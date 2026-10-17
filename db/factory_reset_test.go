package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestFactoryResetIsolationRollbackAndFreshState(t *testing.T) {
	source, _, err := DSN()
	if err != nil {
		t.Skip("isolated postgres unavailable")
	}
	u, err := url.Parse(source)
	if err != nil || u.Scheme == "" {
		t.Skip("URL database configuration required")
	}
	admin, err := sql.Open("pgx", source)
	if err != nil {
		t.Fatal(err)
	}
	defer admin.Close()
	name := fmt.Sprintf("wsartex_factory_reset_%d", time.Now().UnixNano())
	if _, err = admin.Exec(`CREATE DATABASE "` + name + `"`); err != nil {
		t.Skip("test role cannot create an isolated database")
	}
	defer admin.Exec(`DROP DATABASE "` + name + `" WITH (FORCE)`)
	u.Path = "/" + name
	dsn := u.String()
	pg, err := Open(dsn)
	if err != nil {
		t.Fatal(err)
	}
	if err = pg.EnsureLLMRecordsTable(); err != nil {
		t.Fatal(err)
	}
	if err = pg.EnsureLLMUsageTable(); err != nil {
		t.Fatal(err)
	}
	if err = pg.SetSetting("auth.password_hash", "sentinel-hash"); err != nil {
		t.Fatal(err)
	}
	if _, err = pg.Exec(`INSERT INTO companies(name,nkey) VALUES ('one','one'),('two','two')`); err != nil {
		t.Fatal(err)
	}
	if _, err = pg.Exec(`CREATE TABLE unrelated_data(id integer)`); err != nil {
		t.Fatal(err)
	}
	pg.Close()
	called := false
	if err = FactoryReset(context.Background(), dsn, func() error { called = true; return nil }); err == nil || called {
		t.Fatal("unexpected tables were not rejected before deletion")
	}
	check, err := sql.Open("pgx", dsn)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = check.Exec(`DROP TABLE unrelated_data`); err != nil {
		t.Fatal(err)
	}
	// A second running instance must block the destructive operation.
	if err = FactoryReset(context.Background(), dsn, func() error { called = true; return nil }); err == nil || called {
		t.Fatal("live database clients did not block reset")
	}
	check.Close()
	fileFailure := errors.New("file cleanup failed")
	if err = FactoryReset(context.Background(), dsn, func() error { return fileFailure }); !errors.Is(err, fileFailure) {
		t.Fatalf("cleanup error=%v", err)
	}
	check, err = sql.Open("pgx", dsn)
	if err != nil {
		t.Fatal(err)
	}
	var hash string
	if err = check.QueryRow(`SELECT value FROM settings WHERE key='auth.password_hash'`).Scan(&hash); err != nil || hash != "sentinel-hash" {
		t.Fatal("file failure did not roll back password deletion")
	}
	check.Close()
	dir := filepath.Join(t.TempDir(), "data")
	if err = os.MkdirAll(dir, 0o700); err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(dir, "sentinel"), []byte("private test data"), 0o600); err != nil {
		t.Fatal(err)
	}
	if err = FactoryReset(context.Background(), dsn, func() error { return os.RemoveAll(dir) }); err != nil {
		t.Fatal(err)
	}
	if _, err = os.Stat(dir); !os.IsNotExist(err) {
		t.Fatal("runtime files were not permanently removed")
	}
	check, err = sql.Open("pgx", dsn)
	if err != nil {
		t.Fatal(err)
	}
	var count int
	if err = check.QueryRow(`SELECT count(*) FROM settings`).Scan(&count); err != nil || count != 0 {
		t.Fatal("settings were retained")
	}
	var id int
	if err = check.QueryRow(`INSERT INTO companies(name,nkey) VALUES ('fresh','fresh') RETURNING id`).Scan(&id); err != nil || id != 1 {
		t.Fatalf("sequence id=%d err=%v", id, err)
	}
	check.Close()
	pg, err = Open(dsn)
	if err != nil {
		t.Fatal(err)
	}
	defer pg.Close()
	if _, exists, err := pg.GetSetting("auth.password_hash"); err != nil || exists {
		t.Fatal("password was recreated")
	}
	if builtin, err := pg.GetAgentByKey("worker"); err != nil || builtin == nil {
		t.Fatal("built-in defaults were not restored on startup")
	}
}
