package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"wsartex/config"
	"wsartex/db"
	"wsartex/server"
)

// Keep the writer reachable and open until process exit. The replacement cannot
// delete files until the OS closes it, after every old goroutine has stopped.
var resetExitPipe *os.File
var resetExitID string

func resetPaths(dataDir, keyDir string) (string, string, error) {
	base, err := filepath.Abs(keyDir)
	if err != nil {
		return "", "", err
	}
	data, err := filepath.Abs(dataDir)
	if err != nil {
		return "", "", err
	}
	if filepath.Clean(data) != filepath.Join(base, "data") {
		return "", "", fmt.Errorf("清除数据仅支持程序目录下的 data 目录")
	}
	if st, err := os.Lstat(data); err == nil && (st.Mode()&os.ModeSymlink != 0 || !st.IsDir()) {
		return "", "", fmt.Errorf("data 必须是本项目的普通目录")
	} else if err != nil && !os.IsNotExist(err) {
		return "", "", err
	}
	return data, base, nil
}

func startResetReplacement(dataDir, keyDir, addr, proxy string) (string, error) {
	data, base, err := resetPaths(dataDir, keyDir)
	if err != nil {
		return "", err
	}
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	cfg, err := filepath.Abs(config.Path())
	if err != nil {
		return "", err
	}
	// Never remove the configuration needed to reconnect, or a custom skill tree.
	for _, protected := range []string{cfg, config.SkillDir()} {
		p, err := filepath.Abs(protected)
		if err != nil {
			return "", err
		}
		if p == data || strings.HasPrefix(p, data+string(filepath.Separator)) {
			return "", fmt.Errorf("配置或 skill 目录不能位于 data 中")
		}
	}
	var nonce [16]byte
	if _, err := rand.Read(nonce[:]); err != nil {
		return "", err
	}
	id := hex.EncodeToString(nonce[:])
	reader, writer, err := os.Pipe()
	if err != nil {
		return "", err
	}
	defer reader.Close()
	null, err := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
	if err != nil {
		writer.Close()
		return "", err
	}
	defer null.Close()
	cmd := exec.Command(exe, "-addr", addr, "-data", data, "-proxy", proxy, "-factory-reset", id)
	cmd.Dir = base
	cmd.Env = append(os.Environ(), "WSARTEX_CONFIG="+cfg)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = reader, null, null
	if err := cmd.Start(); err != nil {
		writer.Close()
		return "", err
	}
	resetExitPipe, resetExitID = writer, id
	// The child is intentionally independent of HTTP request cancellation.
	go cmd.Wait()
	return id, nil
}

func finishFactoryReset(id, dataDir, keyDir string) server.FactoryResetResult {
	result := server.FactoryResetResult{ID: id, Status: "failed"}
	// A missing/incorrect handoff never authorizes deletion. No password is
	// persisted or passed on a command line; this pipe only carries the job id.
	handoff, err := io.ReadAll(io.LimitReader(os.Stdin, 128))
	os.Stdin.Close()
	if err != nil || string(handoff) != id {
		return result
	}
	data, base, err := resetPaths(dataDir, keyDir)
	if err != nil {
		return result
	}
	dsn, _, err := config.PostgresDSN()
	if err != nil {
		return result
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	err = db.FactoryReset(ctx, dsn, func() error {
		// Deliberately bypass Trash/staging/backups for the explicit factory-reset
		// action. RemoveAll unlinks symlinks within data without following them.
		if err := os.RemoveAll(data); err != nil {
			return err
		}
		if err := os.Remove(filepath.Join(base, "jwt.key")); err != nil && !os.IsNotExist(err) {
			return err
		}
		return nil
	})
	if err == nil {
		result.Status = "complete"
	}
	return result
}

func resetLog(dataDir string) error {
	if err := os.MkdirAll(dataDir, 0o700); err != nil {
		return err
	}
	f, err := os.OpenFile(filepath.Join(dataDir, "wsartex-launcher.log"), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	os.Stdout, os.Stderr = f, f
	return os.WriteFile(filepath.Join(dataDir, "wsartex-launcher.pid"), []byte(fmt.Sprintln(os.Getpid())), 0o600)
}
