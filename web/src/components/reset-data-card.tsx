"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { LoaderCircleIcon, Trash2Icon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";

const pendingKey = "wsartex_factory_reset_pending";

async function waitForReset(id: string, signal: AbortSignal) {
  const deadline = Date.now() + 120_000;
  while (Date.now() < deadline && !signal.aborted) {
    const request = new AbortController();
    const abort = () => request.abort();
    signal.addEventListener("abort", abort, { once: true });
    const timeout = setTimeout(abort, 3000);
    let status = "";
    try {
      const response = await fetch("/api/health", { cache: "no-store", signal: request.signal });
      if (response.ok) {
        const health = await response.json();
        if (health.factory_reset?.id === id) status = health.factory_reset.status;
      }
    } catch {
      // The old server exits before its replacement starts listening.
    } finally {
      clearTimeout(timeout);
      signal.removeEventListener("abort", abort);
    }
    if (status === "complete") return;
    if (status === "failed") throw new Error("清除未完成。服务已恢复，请重新进入面板后检查数据并重试。");
    await new Promise((resolve) => setTimeout(resolve, 600));
  }
  throw new Error("暂时无法确认清除结果，请稍后重新进入面板检查。请勿重复提交。");
}

function enterSetup() {
  localStorage.clear();
  sessionStorage.clear();
  for (const cookie of document.cookie.split(";")) {
    const name = cookie.split("=")[0].trim();
    if (name) {
      // biome-ignore lint/suspicious/noDocumentCookie: Expire this origin's preferences and auth cookies during an explicit factory reset.
      document.cookie = `${name}=; Max-Age=0; path=/; SameSite=Lax`;
    }
  }
  window.location.replace("/setup");
}

export function ResetDataCard({ disabled }: { disabled: boolean }) {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [failed, setFailed] = useState(false);
  const controller = useRef<AbortController | null>(null);

  const monitor = useCallback(async (id: string, signal: AbortSignal) => {
    try {
      await waitForReset(id, signal);
      if (!signal.aborted) enterSetup();
    } catch (e) {
      if (signal.aborted) return;
      setError((e as Error).message);
      setFailed(true);
      setBusy(false);
      sessionStorage.removeItem(pendingKey);
    }
  }, []);

  useEffect(() => {
    const id = sessionStorage.getItem(pendingKey);
    if (id) {
      const current = new AbortController();
      controller.current = current;
      setOpen(true);
      setBusy(true);
      setAccepted(true);
      void monitor(id, current.signal);
    }
    return () => controller.current?.abort();
  }, [monitor]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !password) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.resetAllData(password);
      setPassword("");
      setAccepted(true);
      sessionStorage.setItem(pendingKey, result.id);
      const current = new AbortController();
      controller.current = current;
      await monitor(result.id, current.signal);
    } catch (e) {
      setPassword("");
      setError((e as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <Card className="mb-4 break-inside-avoid border-destructive/40 md:mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base text-destructive">
            <Trash2Icon className="size-4" />
            清除所有数据
          </CardTitle>
          <CardDescription>
            永久清除任务、资产、对话、流量、工作区文件、模型与系统配置及登录密码，恢复到首次使用状态。
            数据不会进入回收站，也不会自动备份。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Button
            variant="destructive"
            disabled={disabled || busy}
            onClick={() => {
              setPassword("");
              setError("");
              setAccepted(false);
              setFailed(false);
              setOpen(true);
            }}
          >
            清除所有数据
          </Button>
        </CardContent>
      </Card>
      <Dialog
        open={open}
        onOpenChange={(next) => {
          if (!busy) {
            setOpen(next);
            setPassword("");
          }
        }}
      >
        <DialogContent
          className="sm:max-w-lg"
          onInteractOutside={(e) => {
            if (busy) e.preventDefault();
          }}
          onEscapeKeyDown={(e) => {
            if (busy) e.preventDefault();
          }}
        >
          <DialogHeader>
            <DialogTitle>永久清除所有数据</DialogTitle>
            <DialogDescription>
              此操作无法撤销。所有历史数据、配置和登录密码都会被永久删除，不进入回收站、不自动备份。
              正在运行的任务会停止，完成后需要重新设置密码和 LLM。程序文件与随项目提供的 skills 保留。
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={submit} className="space-y-5">
            {!accepted && (
              <div className="space-y-2">
                <Label htmlFor="reset-current-password">当前登录密码</Label>
                <Input
                  id="reset-current-password"
                  type="password"
                  autoComplete="current-password"
                  value={password}
                  disabled={busy}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="输入当前密码以确认"
                />
              </div>
            )}
            {busy && (
              <p role="status" className="flex items-center gap-2 text-sm">
                <LoaderCircleIcon className="size-4 animate-spin" />
                {accepted ? "正在清除数据并重新启动，请勿关闭页面…" : "正在验证密码…"}
              </p>
            )}
            {error && (
              <p role="alert" className="text-destructive text-sm">
                {error}
              </p>
            )}
            <DialogFooter>
              {failed ? (
                <Button type="button" onClick={enterSetup}>
                  重新进入面板
                </Button>
              ) : (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    disabled={busy}
                    onClick={() => {
                      setOpen(false);
                      setPassword("");
                    }}
                  >
                    取消
                  </Button>
                  <Button type="submit" variant="destructive" disabled={busy || !password}>
                    确认永久清除
                  </Button>
                </>
              )}
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}
