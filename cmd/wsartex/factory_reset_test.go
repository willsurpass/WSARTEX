package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestResetPathsRejectsExternalAndSymlinkDirectories(t *testing.T) {
	base := t.TempDir()
	if _, _, err := resetPaths(base, base); err == nil {
		t.Fatal("project root accepted as data")
	}
	if _, _, err := resetPaths(filepath.Join(base, ".."), base); err == nil {
		t.Fatal("parent directory accepted")
	}
	data := filepath.Join(base, "data")
	if _, _, err := resetPaths(data, base); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(t.TempDir(), data); err != nil {
		t.Skip("symlinks unavailable")
	}
	if _, _, err := resetPaths(data, base); err == nil {
		t.Fatal("symlink data root accepted")
	}
}
