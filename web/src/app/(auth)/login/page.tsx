"use client";

import { useEffect, useRef, useState } from "react";

import { useRouter } from "next/navigation";

import { AlertTriangle, ShieldCheck } from "lucide-react";

import { BrandWordmark } from "@/components/brand-wordmark";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogClose, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);
  const [agreed, setAgreed] = useState(false);
  const [termsOpen, setTermsOpen] = useState(false);
  const [readToEnd, setReadToEnd] = useState(false);
  const termsBodyRef = useRef<HTMLDivElement>(null);

  // 滚动到条款底部（含无需滚动即可完整展示的情况）方可点击「确认」。
  function handleTermsScroll() {
    const el = termsBodyRef.current;
    if (!el) return;
    if (el.scrollTop + el.clientHeight >= el.scrollHeight - 8) setReadToEnd(true);
  }

  useEffect(() => {
    if (!termsOpen) return;
    // 打开时重置，并处理内容本就不足一屏、无法触发滚动的场景。
    setReadToEnd(false);
    const el = termsBodyRef.current;
    if (el && el.scrollHeight <= el.clientHeight + 8) setReadToEnd(true);
  }, [termsOpen]);

  useEffect(() => {
    // 已登录直接进主界面（静态导出下无 middleware 代劳这层跳转）。
    const token = auth.getToken();
    if (token) {
      // localStorage 可能仍有凭据但 cookie 已丢失。先同步，再发起全新请求，
      // 避免服务端守卫或路由缓存把跳转送回仍处于 checking 状态的登录页。
      auth.setToken(token);
      window.location.replace("/function/tasks");
      return;
    }
    api
      .authStatus()
      .then(({ initialized }) => {
        if (!initialized) router.replace("/setup");
      })
      .catch(() => setError("无法连接到后端服务"))
      .finally(() => setChecking(false));
  }, [router]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!agreed) {
      setError("请先阅读并了解《使用须知》");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const { token } = await api.login("WSARTEX", password);
      auth.setToken(token);
      window.location.replace("/function/tasks");
    } catch {
      setError("用户名或密码错误");
    } finally {
      setLoading(false);
    }
  }

  if (checking) {
    return (
      <div role="status" className="flex min-h-dvh items-center justify-center text-muted-foreground">
        正在检查登录状态…
      </div>
    );
  }

  return (
    <div className="flex h-dvh">
      {/* Left panel */}
      <div className="hidden flex-col items-center justify-center bg-black p-12 text-center lg:flex lg:w-1/3">
        <div className="relative flex items-center justify-center">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/brand/logo-dark.svg" alt="WSARTEX" width={320} height={320} className="h-auto w-80 max-w-full" />
        </div>
      </div>

      {/* Right panel */}
      <div className="flex w-full items-center justify-center bg-background p-8 lg:w-2/3">
        <div className="w-full max-w-md space-y-10 py-24 lg:py-32">
          <div className="space-y-4 text-center">
            <BrandWordmark className="mx-auto mb-8 w-48 lg:hidden" />
            <h2 className="text-2xl font-medium tracking-tight">登录</h2>
            <p className="mx-auto max-w-xl text-muted-foreground">欢迎回来，请输入密码以继续使用 WSARTEX</p>
          </div>
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div className="space-y-1.5">
              <Label htmlFor="username">用户名</Label>
              <Input id="username" value="WSARTEX" readOnly className="bg-muted text-muted-foreground" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">密码</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="请输入密码"
                autoFocus
                autoComplete="current-password"
              />
            </div>
            <div className="flex items-start gap-2">
              <Checkbox
                id="agree-terms"
                checked={agreed}
                onCheckedChange={(v) => setAgreed(v === true)}
                className="mt-0.5"
              />
              <Label htmlFor="agree-terms" className="text-sm font-normal leading-relaxed text-muted-foreground">
                我已阅读并了解
                <button
                  type="button"
                  onClick={() => setTermsOpen(true)}
                  className="mx-0.5 font-medium text-primary underline-offset-4 hover:underline"
                >
                  《使用须知》
                </button>
              </Label>
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={loading || !password || !agreed}>
              {loading ? "登录中..." : "登录"}
            </Button>
          </form>
        </div>
      </div>

      <Dialog open={termsOpen} onOpenChange={setTermsOpen}>
        <DialogContent className="gap-0 p-0 sm:max-w-2xl">
          <DialogHeader className="flex-row items-center gap-3 border-b px-6 py-4">
            <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="size-5" />
            </div>
            <div className="space-y-0.5">
              <DialogTitle className="text-base">WSARTEX 使用须知与免责声明</DialogTitle>
              <p className="text-xs text-muted-foreground">
                版本 v1.1 · 更新日期 2026-10-18 · 请在登录前阅读以下许可与使用提示
              </p>
            </div>
          </DialogHeader>

          <div
            ref={termsBodyRef}
            onScroll={handleTermsScroll}
            className="max-h-[60vh] space-y-5 overflow-y-auto px-6 py-5 text-sm leading-relaxed text-muted-foreground"
          >
            <p className="rounded-lg border bg-muted/40 p-3 text-foreground/80">
              本声明介绍 WSARTEX 的开源许可、使用建议及风险。软件许可权利义务以随附的 LICENSE
              及第三方许可证为准；使用建议不构成对开源许可证所授予权利的额外限制。
            </p>

            <section className="space-y-1.5">
              <h4 className="flex items-center gap-2 font-medium text-foreground">
                <span className="flex size-5 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  1
                </span>
                第一条 · 定义与开源许可
              </h4>
              <p className="pl-7">
                本软件基于 ARTEX 修改，采用 GNU Affero General Public License 第 3 版或后续版本（AGPL-3.0-or-later）。
                您可按协议使用、复制、修改和分发，也可商业使用。分发时须保留许可及版权声明，并按协议提供对应源码；修改版支持用户通过网络交互时，须向这些用户免费提供完整对应源码的获取方式。
                第三方组件仍适用各自许可证，来源与版权见仓库 NOTICE.md。源码与修改记录可在
                <a
                  className="mx-0.5 text-primary underline underline-offset-4"
                  href="https://github.com/willsurpass/WSARTEX"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  WSARTEX 仓库
                </a>
                查看。
              </p>
            </section>

            <section className="space-y-1.5">
              <h4 className="flex items-center gap-2 font-medium text-foreground">
                <span className="flex size-5 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  2
                </span>
                第二条 · 使用建议
              </h4>
              <p className="pl-7">
                建议先在本地隔离靶场中学习、研究和验证。对实际系统开展安全测试时，应事先取得必要授权，明确目标范围、测试方式和数据处理边界，并遵守适用法律法规。这些建议不限制
                AGPL 所授予的权利，也不代替目标系统所有者的授权。
              </p>
            </section>

            <section className="space-y-2">
              <h4 className="flex items-center gap-2 font-medium text-destructive">
                <span className="flex size-5 items-center justify-center rounded-md bg-destructive/10 text-xs font-semibold text-destructive">
                  3
                </span>
                <AlertTriangle className="size-4" />
                第三条 · 合法使用与风险
              </h4>
              <ul className="ml-7 list-decimal space-y-1.5 rounded-lg border border-destructive/20 bg-destructive/5 p-3 pl-8 text-foreground/80 marker:text-destructive/70">
                <li>对系统开展安全测试前，请取得必要授权，并在约定范围和时间内操作；</li>
                <li>严禁将本软件用于非法入侵、数据窃取、勒索、拒绝服务（DoS/DDoS）或任何破坏性、犯罪性活动；</li>
                <li>分发软件时，应按适用许可证保留相应版权、许可和免责声明；</li>
                <li>严禁从事任何违反您所在国家或地区法律、法规及监管规定的行为。</li>
              </ul>
            </section>

            <section className="space-y-1.5">
              <h4 className="flex items-center gap-2 font-medium text-foreground">
                <span className="flex size-5 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  4
                </span>
                第四条 · 知识产权
              </h4>
              <p className="pl-7">
                原始 ARTEX 代码的版权归原作者及贡献者所有，WSARTEX 新增和修改部分的版权归相应贡献者所有。
                第三方组件保留各自版权与许可。相关来源与修改说明见仓库 NOTICE.md，软件权利义务以适用许可证为准。
              </p>
            </section>

            <section className="space-y-1.5">
              <h4 className="flex items-center gap-2 font-medium text-foreground">
                <span className="flex size-5 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  5
                </span>
                第五条 · 数据与隐私
              </h4>
              <p className="pl-7">
                本软件由您自行部署。配置
                LLM、MCP、通知或其他外部服务后，相关请求可能包含任务内容、工具输出等数据，请自行评估接收方和数据处理范围。开源许可要求提供程序对应源码，不要求公开数据库、密码、API
                Key 等运行数据或凭据。
              </p>
            </section>

            <section className="space-y-1.5">
              <h4 className="flex items-center gap-2 font-medium text-foreground">
                <span className="flex size-5 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  6
                </span>
                第六条 · 合规与法律责任
              </h4>
              <p className="pl-7">
                您应自行遵守所在国家或地区关于网络安全、数据安全与个人信息保护、计算机犯罪等方面的全部法律法规（在中国大陆包括但不限于《网络安全法》《数据安全法》《个人信息保护法》及相关司法解释）。
                <span className="font-medium text-foreground">
                  {" "}
                  使用者应保护数据、遵守测试授权范围，并依法承担相应责任。作者及贡献者的免责范围以适用许可证和法律为准。
                </span>
              </p>
            </section>

            <section className="space-y-1.5">
              <h4 className="flex items-center gap-2 font-medium text-foreground">
                <span className="flex size-5 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  7
                </span>
                第七条 · 免责声明与责任限制
              </h4>
              <p className="pl-7">
                本软件按"现状（AS IS）"与"现有（AS
                AVAILABLE）"状态提供，不附带任何明示或默示的担保，包括但不限于对适销性、特定用途适用性、准确性及不侵权的担保。在适用法律允许的最大范围内，本软件作者及贡献者不对因使用或无法使用本软件（无论使用方式是否得当）而导致的任何直接、间接、偶然、特殊或后果性损失承担责任，包括但不限于数据丢失、系统损坏、业务中断、利润损失或法律纠纷。
              </p>
            </section>

            <section className="space-y-1.5">
              <h4 className="flex items-center gap-2 font-medium text-foreground">
                <span className="flex size-5 items-center justify-center rounded-md bg-muted text-xs font-semibold text-muted-foreground">
                  8
                </span>
                第八条 · 许可证与声明的关系
              </h4>
              <p className="pl-7">
                本声明仅用于解释许可证和提示使用风险，不增加用途限制，也不缩减 AGPL
                或第三方许可证授予的权利。如摘要与许可证存在不一致，以相应许可证正文为准。后续声明更新不撤销既有版本依据许可证已经授予的权利。
              </p>
            </section>
          </div>

          <DialogFooter className="mx-0 mb-0 flex-col items-stretch gap-2 rounded-b-xl px-6 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-xs text-muted-foreground">
              {readToEnd ? "您已浏览全部条款" : "请将条款滚动至底部后再确认"}
            </p>
            <DialogClose asChild>
              <Button
                type="button"
                disabled={!readToEnd}
                onClick={() => {
                  setAgreed(true);
                  setError("");
                }}
              >
                我已阅读并了解全部内容
              </Button>
            </DialogClose>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
