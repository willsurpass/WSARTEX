package server

import (
	"context"
	"net/http"
	"sync"
	"time"

	"wsartex/agent"
	"wsartex/sidequestion"

	"golang.org/x/crypto/bcrypt"
)

// Called after admission has closed and the server's background context has
// been cancelled. A failed drain prevents the replacement from deleting data.
func (s *Server) WaitForFactoryReset(ctx context.Context) error {
	done := make(chan struct{})
	go func() {
		defer close(done)
		s.chatMu.Lock()
		for _, cancel := range s.chatCancel {
			cancel(agent.AbortShutdown)
		}
		s.chatMu.Unlock()
		for _, ch := range s.cancelSideWhere(func(sidequestion.Parent) bool { return true }) {
			<-ch
		}
		for _, task := range s.m.List() {
			s.engine.StopTask(task.ID)
		}
		s.archiveWG.Wait()
		if s.side != nil {
			<-s.side.done
		}
		for {
			s.chatMu.Lock()
			busy := len(s.chatBusy) != 0
			s.chatMu.Unlock()
			if !busy {
				return
			}
			select {
			case <-ctx.Done():
				return
			case <-time.After(20 * time.Millisecond):
			}
		}
	}()
	select {
	case <-ctx.Done():
		return ctx.Err()
	case <-done:
		return ctx.Err()
	}
}

type FactoryResetResult struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

type factoryResetControl struct {
	mu      sync.Mutex
	request func() (string, error)
	result  FactoryResetResult
	pending bool
}

// ConfigureFactoryReset wires process replacement owned by the executable.
// Test/embedded servers without this hook cannot erase their data via HTTP.
func (s *Server) ConfigureFactoryReset(request func() (string, error), result FactoryResetResult) {
	s.factoryReset.mu.Lock()
	defer s.factoryReset.mu.Unlock()
	s.factoryReset.request = request
	s.factoryReset.result = result
}

func (s *Server) factoryResetSnapshot() (FactoryResetResult, bool) {
	s.factoryReset.mu.Lock()
	defer s.factoryReset.mu.Unlock()
	return s.factoryReset.result, s.factoryReset.pending
}

func (s *Server) resetAllData(w http.ResponseWriter, r *http.Request) {
	pg := s.pg(w)
	if pg == nil {
		return
	}
	var req struct {
		Password string `json:"password"`
		Confirm  bool   `json:"confirm"`
	}
	if err := decode(r, &req); err != nil || req.Password == "" || !req.Confirm {
		writeErr(w, http.StatusBadRequest, "请输入当前密码并确认永久清除所有数据")
		return
	}
	hash, _, err := pg.GetSetting(authPassKey)
	if err != nil {
		writeErr(w, 503, errDataSourceUnavailable)
		return
	}
	if hash == "" {
		writeErr(w, 403, "尚未设置密码，无需清除")
		return
	}
	// A password mismatch must not log the operator out (the generic client
	// treats 401 as an expired session).
	if bcrypt.CompareHashAndPassword([]byte(hash), []byte(req.Password)) != nil {
		writeErr(w, http.StatusForbidden, "当前密码不正确，数据未清除")
		return
	}
	s.factoryReset.mu.Lock()
	defer s.factoryReset.mu.Unlock()
	if s.factoryReset.pending {
		writeErr(w, 409, "正在清除数据，请勿重复操作")
		return
	}
	if s.factoryReset.request == nil {
		writeErr(w, 503, "当前启动方式不支持清除数据，请使用项目程序启动")
		return
	}
	id, err := s.factoryReset.request()
	if err != nil {
		writeErr(w, 503, "无法开始清除数据，请检查服务运行环境后重试")
		return
	}
	s.factoryReset.pending = true
	s.factoryReset.result = FactoryResetResult{ID: id, Status: "pending"}
	w.Header().Set("Cache-Control", "no-store")
	writeJSON(w, http.StatusAccepted, s.factoryReset.result)
}
