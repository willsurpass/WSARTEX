package server

import (
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"
)

func TestFactoryResetDrainWaitsForRunningTask(t *testing.T) {
	m := &Manager{tasks: map[string]*Task{"running": {ID: "running"}}}
	e := NewEngine(m)
	s := &Server{m: m, engine: e}
	rt := e.registerTaskRoutines(context.Background(), "running", 1)
	cancelled := make(chan struct{})
	release := make(chan struct{})
	runTaskRoutine(rt, func(ctx context.Context) {
		<-ctx.Done()
		close(cancelled)
		<-release // final writes / Session.Close must complete before deletion
	})
	ctx, cancel := context.WithTimeout(context.Background(), time.Second)
	defer cancel()
	done := make(chan error, 1)
	go func() { done <- s.WaitForFactoryReset(ctx) }()
	select {
	case <-cancelled:
	case <-ctx.Done():
		close(release)
		t.Fatal("running task was not cancelled")
	}
	select {
	case <-done:
		close(release)
		t.Fatal("reset proceeded before the running task finished")
	default:
	}
	close(release)
	select {
	case err := <-done:
		if err != nil {
			t.Fatal(err)
		}
	case <-ctx.Done():
		t.Fatal("reset did not finish draining")
	}
}

func TestFactoryResetRequiresSessionPasswordAndConfirmation(t *testing.T) {
	m, err := NewManager(t.TempDir(), "")
	if err != nil {
		t.Skip("isolated postgres unavailable")
	}
	t.Cleanup(func() { _ = m.Close() })
	previous, existed, err := m.pg.GetSetting(authPassKey)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if existed {
			_ = m.pg.SetSetting(authPassKey, previous)
		} else {
			_, _ = m.pg.Exec(`DELETE FROM settings WHERE key=$1`, authPassKey)
		}
	})
	hash, _ := bcrypt.GenerateFromPassword([]byte("factory-reset-test-password"), bcrypt.MinCost)
	if err := m.pg.SetSetting(authPassKey, string(hash)); err != nil {
		t.Fatal(err)
	}
	s := &Server{m: m, jwtKey: []byte("factory-reset-test-signing-key-32-bytes")}
	calls := 0
	s.ConfigureFactoryReset(func() (string, error) { calls++; return "test-reset-job", nil }, FactoryResetResult{})
	token, err := signJWT(s.jwtKey)
	if err != nil {
		t.Fatal(err)
	}
	handler := s.Handler()
	request := func(body, credential string) *httptest.ResponseRecorder {
		r := httptest.NewRequest("POST", "/api/settings/reset", strings.NewReader(body))
		if credential != "" {
			r.Header.Set("Authorization", "Bearer "+credential)
		}
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		return w
	}
	for _, tc := range []struct {
		name, body, token string
		status            int
	}{
		{"no session", `{"password":"factory-reset-test-password","confirm":true}`, "", 401},
		{"invalid session", `{"password":"factory-reset-test-password","confirm":true}`, "invalid", 401},
		{"missing password", `{"confirm":true}`, token, 400},
		{"missing confirmation", `{"password":"factory-reset-test-password"}`, token, 400},
		{"wrong password", `{"password":"wrong-password","confirm":true}`, token, 403},
	} {
		t.Run(tc.name, func(t *testing.T) {
			w := request(tc.body, tc.token)
			if w.Code != tc.status {
				t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
			}
			if calls != 0 {
				t.Fatal("unauthorized reset was started")
			}
			got, _, err := m.pg.GetSetting(authPassKey)
			if err != nil || got != string(hash) {
				t.Fatal("password changed on rejected request")
			}
		})
	}
	s.ConfigureFactoryReset(func() (string, error) { return "", errors.New("replacement unavailable") }, FactoryResetResult{})
	if w := request(`{"password":"factory-reset-test-password","confirm":true}`, token); w.Code != 503 {
		t.Fatalf("replacement failure status=%d", w.Code)
	}
	if _, pending := s.factoryResetSnapshot(); pending {
		t.Fatal("failed start left admission closed")
	}
	s.ConfigureFactoryReset(func() (string, error) { calls++; return "test-reset-job", nil }, FactoryResetResult{})
	w := request(`{"password":"factory-reset-test-password","confirm":true}`, token)
	if w.Code != http.StatusAccepted {
		t.Fatalf("status=%d body=%s", w.Code, w.Body.String())
	}
	var result FactoryResetResult
	if err := json.Unmarshal(w.Body.Bytes(), &result); err != nil || result.ID != "test-reset-job" || result.Status != "pending" {
		t.Fatalf("unexpected result: %s", w.Body.String())
	}
	if w := request(`{"password":"factory-reset-test-password","confirm":true}`, token); w.Code != 503 {
		t.Fatalf("duplicate request status=%d", w.Code)
	}
	if calls != 1 {
		t.Fatalf("replacement starts=%d", calls)
	}
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("POST", "/api/auth/init", strings.NewReader(`{"password":"another-password"}`)))
	if w.Code != 503 {
		t.Fatal("password initialization was allowed during reset")
	}
	w = httptest.NewRecorder()
	handler.ServeHTTP(w, httptest.NewRequest("GET", "/api/health", nil))
	if w.Code != 200 || !strings.Contains(w.Body.String(), "test-reset-job") {
		t.Fatalf("reset health unavailable: %s", w.Body.String())
	}
}
