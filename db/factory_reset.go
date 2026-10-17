package db

import (
	"context"
	"database/sql"
	"fmt"
	"regexp"
	"strings"
	"time"
)

// FactoryReset empties this application's tables and resets their sequences.
// The caller must first stop the old process, including all background writers.
// Files are permanently removed before the transaction commits; a file error
// rolls the database back, keeping the password available for another attempt.
func FactoryReset(ctx context.Context, dsn string, removeFiles func() error) error {
	conn, err := sql.Open("pgx", dsn)
	if err != nil {
		return err
	}
	defer conn.Close()
	conn.SetMaxOpenConns(1)
	tx, err := conn.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err = tx.ExecContext(ctx, `SET LOCAL lock_timeout = '5s'`); err != nil {
		return err
	}
	if _, err = tx.ExecContext(ctx, `SELECT pg_advisory_xact_lock($1)`, schemaMigrationLockKey); err != nil {
		return err
	}
	deadline := time.Now().Add(5 * time.Second)
	for {
		var clients int
		if err = tx.QueryRowContext(ctx, `SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()`).Scan(&clients); err != nil {
			return err
		}
		if clients == 0 {
			break
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("数据库仍被其他进程使用，请先关闭其他实例")
		}
		// PostgreSQL can need a moment to reap the old process's connections.
		if _, err = tx.ExecContext(ctx, `SELECT pg_stat_clear_snapshot()`); err != nil {
			return err
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(50 * time.Millisecond):
		}
	}
	known := map[string]bool{"llm_records": true, "llm_usage": true}
	for _, match := range regexp.MustCompile(`(?i)CREATE TABLE IF NOT EXISTS\s+(\w+)`).FindAllStringSubmatch(schemaSQL, -1) {
		known[match[1]] = true
	}
	rows, err := tx.QueryContext(ctx, `SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename`)
	if err != nil {
		return err
	}
	var tables []string
	for rows.Next() {
		var name string
		if err = rows.Scan(&name); err != nil {
			rows.Close()
			return err
		}
		if !known[name] {
			rows.Close()
			return fmt.Errorf("数据库包含非本项目的数据表，已停止清除")
		}
		tables = append(tables, `public."`+name+`"`)
	}
	if err = rows.Err(); err != nil {
		rows.Close()
		return err
	}
	rows.Close()
	if len(tables) == 0 {
		return fmt.Errorf("项目数据库尚未初始化")
	}
	// RESTRICT prevents a foreign table outside the project from being cleared
	// through a cross-schema foreign key.
	if _, err = tx.ExecContext(ctx, `TRUNCATE TABLE `+strings.Join(tables, ",")+` RESTART IDENTITY RESTRICT`); err != nil {
		return err
	}
	if err = removeFiles(); err != nil {
		return err
	}
	return tx.Commit()
}
