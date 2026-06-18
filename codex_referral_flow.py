#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Codex 全自動邀請流程
====================
一條命令完成：母號登入 → 發送邀請 → 子號登入 → 激活

用法：
  python codex_referral_flow.py \\
    --seeds seeds.json \\
    --domain dfhdg.store \\
    --per-account 5 \\
    --oidc-sso-url https://sso.example.com \\
    --oidc-sso-admin-token YOUR_TOKEN \\
    --oidc-sso-invite-code JOIN-2026

  # 完整參數
  python codex_referral_flow.py \\
    --seeds seeds.json \\
    --domain dfhdg.store \\
    --per-account 5 \\
    --concurrency 10 \\
    --oidc-sso-url https://sso.example.com \\
    --oidc-sso-admin-token YOUR_TOKEN \\
    --oidc-sso-invite-code JOIN-2026 \\
    --out-dir ./runs/example \\
    --proxy http://127.0.0.1:7897
"""

import os
import sys
import json
import time
import argparse
import subprocess
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")


def log(msg: str, symbol: str = "*", level: str = "INFO") -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"[{ts}] [{symbol}] [{level}] {msg}", flush=True)


def run_command(cmd: list, step_name: str) -> bool:
    """執行外部命令，返回是否成功"""
    log(f"執行: {' '.join(cmd)}", "→")
    try:
        result = subprocess.run(
            cmd,
            check=False,
            text=True,
            capture_output=False,
        )
        if result.returncode == 0:
            log(f"{step_name} 完成", "✓")
            return True
        else:
            log(f"{step_name} 失敗 (exit code: {result.returncode})", "✗", "ERROR")
            return False
    except Exception as e:
        log(f"{step_name} 異常: {e}", "✗", "ERROR")
        return False


def extract_invited_emails(results_json: Path, output_txt: Path) -> int:
    """從邀請結果 JSON 中提取被邀請的郵箱"""
    if not results_json.exists():
        log(f"邀請結果文件不存在: {results_json}", "✗", "ERROR")
        return 0

    with open(results_json, encoding="utf-8") as f:
        data = json.load(f)

    emails = []
    for account in data:
        for invite in account.get("invites", []):
            email = invite.get("email", "")
            if email:
                emails.append(email)

    if emails:
        output_txt.parent.mkdir(parents=True, exist_ok=True)
        with open(output_txt, "w", encoding="utf-8") as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
        log(f"提取了 {len(emails)} 個被邀請郵箱", "✓")

    return len(emails)


def generate_account_name(prefix: str = "seed") -> str:
    """生成隨機帳號名稱"""
    import random
    import string
    suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}_{suffix}"


def auto_create_seeds(
    count: int,
    domain: str,
    sso_url: str,
    admin_token: str,
    invite_code: str,
    output_json: Path,
    prefix: str = "seed",
    proxy: str = None,
) -> bool:
    """自動在 SSO 系統中建立母號帳號"""
    import requests
    from concurrent.futures import ThreadPoolExecutor, as_completed

    log(f"自動建立 {count} 個母號帳號", "→")

    # 設定代理
    proxies = None
    if proxy:
        proxies = {
            "http": proxy,
            "https": proxy,
        }

    def create_one_account(idx: int) -> dict:
        account_name = generate_account_name(prefix)
        email = f"{account_name}@{domain}"

        try:
            resp = requests.post(
                f"{sso_url}/api/register",
                headers={
                    "Authorization": f"Bearer {admin_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "account": account_name,
                    "invite_code": invite_code,
                },
                timeout=30,
                proxies=proxies,
            )

            if resp.status_code == 200:
                data = resp.json()
                user = data.get("user", {})
                created = user.get("created", False)
                actual_email = user.get("email", email)

                if created:
                    log(f"[{idx+1}/{count}] ✓ 建立成功: {actual_email}", "✓")
                    return {"email": actual_email, "password": "", "status": "created"}
                else:
                    log(f"[{idx+1}/{count}] ! 帳號已存在: {actual_email}", "!")
                    return {"email": actual_email, "password": "", "status": "exists"}
            else:
                log(f"[{idx+1}/{count}] ✗ 建立失敗: HTTP {resp.status_code} - {resp.text[:100]}", "✗", "ERROR")
                return {"email": email, "password": "", "status": "failed", "error": resp.text[:200]}

        except Exception as e:
            log(f"[{idx+1}/{count}] ✗ 異常: {e}", "✗", "ERROR")
            return {"email": email, "password": "", "status": "error", "error": str(e)}

    results = []
    with ThreadPoolExecutor(max_workers=min(5, count)) as executor:
        futures = {executor.submit(create_one_account, i): i for i in range(count)}
        for future in as_completed(futures):
            results.append(future.result())

    successful = [r for r in results if r["status"] in ("created", "exists")]
    failed = [r for r in results if r["status"] in ("failed", "error")]

    if successful:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(successful, f, indent=2, ensure_ascii=False)
        log(f"成功建立 {len(successful)} 個母號，保存到 {output_json}", "✓")
    else:
        log("沒有成功建立任何母號", "✗", "ERROR")
        return False

    if failed:
        log(f"失敗 {len(failed)} 個", "!", "WARN")

    return len(successful) > 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Codex 全自動邀請流程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--seeds", help="母號 JSON 文件（帳號列表）")
    parser.add_argument("--auto-seeds", type=int, help="自動建立母號數量（與 --seeds 二選一）")
    parser.add_argument("--use-existing-seeds", action="store_true", help="使用已存在的母號（從 out-dir/auto_seeds.json 讀取）")
    parser.add_argument("--seeds-invite-code", help="自動建立母號時使用的邀請碼")
    parser.add_argument("--seeds-prefix", default="seed", help="自動建立母號的前綴 [默認: seed]")
    parser.add_argument("--domain", default="dfhdg.store", help="邀請郵箱域名 [默認: dfhdg.store]")
    parser.add_argument("--per-account", type=int, default=5, help="每個母號邀請數量 [默認: 5]")
    parser.add_argument("--concurrency", type=int, default=10, help="並發數 [默認: 10]")
    parser.add_argument("--out-dir", default="./runs/auto", help="輸出目錄 [默認: ./runs/auto]")
    parser.add_argument("--proxy", default="http://127.0.0.1:7890", help="代理 URL [默認: http://127.0.0.1:7890]")

    parser.add_argument("--oidc-sso-url", required=True, help="OIDC SSO 服務器 URL")
    parser.add_argument("--oidc-sso-admin-token", required=True, help="OIDC SSO ADMIN_TOKEN")
    parser.add_argument("--oidc-sso-invite-code", required=True, help="OIDC SSO 邀請碼（用於子號註冊）")

    parser.add_argument("--skip-seeds-login", action="store_true", help="跳過母號登入（假設已登入）")
    parser.add_argument("--skip-invitations", action="store_true", help="跳過發送邀請（假設已發送）")
    parser.add_argument("--skip-activation", action="store_true", help="跳過子號激活")
    parser.add_argument("--dry-run", action="store_true", help="只預檢，不實際發送")

    args = parser.parse_args()

    # 驗證參數
    seed_sources = sum([
        bool(args.seeds),
        bool(args.auto_seeds),
        bool(args.use_existing_seeds)
    ])
    if seed_sources == 0:
        parser.error("必須提供 --seeds、--auto-seeds 或 --use-existing-seeds")
    if seed_sources > 1:
        parser.error("--seeds、--auto-seeds 和 --use-existing-seeds 只能選一個")
    if args.auto_seeds and not args.seeds_invite_code:
        parser.error("使用 --auto-seeds 時必須提供 --seeds-invite-code")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    seeds_dir = out_dir / "seeds"
    invitees_dir = out_dir / "invitees"
    invite_results = out_dir / "invite_results.json"
    invitees_txt = out_dir / "invitees.txt"
    auto_seeds_json = out_dir / "auto_seeds.json"

    log("=" * 60, "=")
    log("Codex 全自動邀請流程", "=")
    log("=" * 60, "=")
    if args.seeds:
        log(f"母號文件: {args.seeds}")
    else:
        log(f"自動建立母號: {args.auto_seeds} 個")
    log(f"邀請域名: {args.domain}")
    log(f"每號邀請: {args.per_account}")
    log(f"並發數: {args.concurrency}")
    log(f"輸出目錄: {out_dir}")
    log(f"OIDC SSO: {args.oidc_sso_url}")
    log("=" * 60, "=")

    python_exe = sys.executable
    seeds_file = args.seeds

    # ── 步驟 0：處理母號 ─────────────────────────────────────────
    if args.use_existing_seeds:
        if not auto_seeds_json.exists():
            log(f"找不到已存在的母號文件: {auto_seeds_json}", "✗", "ERROR")
            log("請先使用 --auto-seeds 建立母號，或提供 --seeds 參數", "!", "ERROR")
            return 1
        seeds_file = str(auto_seeds_json)
        log(f"使用已存在的母號: {seeds_file}", "✓")

    elif args.auto_seeds:
        log("", "=")
        log("步驟 0/4：自動建立母號", "=")
        log("", "=")

        if not auto_create_seeds(
            count=args.auto_seeds,
            domain=args.domain,
            sso_url=args.oidc_sso_url,
            admin_token=args.oidc_sso_admin_token,
            invite_code=args.seeds_invite_code,
            output_json=auto_seeds_json,
            prefix=args.seeds_prefix,
            proxy=args.proxy,
        ):
            log("自動建立母號失敗，流程終止", "✗", "ERROR")
            return 1

        seeds_file = str(auto_seeds_json)

    # ── 步驟 1：母號登入 ─────────────────────────────────────────
    if not args.skip_seeds_login:
        log("", "=")
        log("步驟 1/4：母號登入", "=")
        log("", "=")

        cmd = [
            python_exe, "codex_protocol_login.py",
            "--json", seeds_file,
            "--out-dir", str(seeds_dir),
            "--concurrency", str(args.concurrency),
            "--oidc-sso-url", args.oidc_sso_url,
            "--oidc-sso-admin-token", args.oidc_sso_admin_token,
        ]
        cmd.extend(["--proxy", args.proxy])

        if not run_command(cmd, "母號登入"):
            log("母號登入失敗，流程終止", "✗", "ERROR")
            return 1
    else:
        log("跳過母號登入", "→")

    # ── 步驟 2：發送邀請 ─────────────────────────────────────────
    if not args.skip_invitations:
        log("", "=")
        log("步驟 2/4：發送邀請", "=")
        log("", "=")

        # 備份已存在的邀請結果
        if invite_results.exists():
            backup_name = invite_results.with_name(
                f"invite_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
            )
            invite_results.rename(backup_name)
            log(f"已備份舊的邀請結果: {backup_name.name}", "✓")

        cmd = [
            python_exe, "codex_invitation_batch.py",
            "--auth-dir", str(seeds_dir),
            "--domain", args.domain,
            "--per-account", str(args.per_account),
            "--concurrency", str(args.concurrency),
            "--out", str(invite_results),
            "--save-back",
        ]
        if args.proxy:
            cmd.extend(["--proxy", args.proxy])
        if args.dry_run:
            cmd.append("--dry-run")

        if not run_command(cmd, "發送邀請"):
            log("發送邀請失敗，流程終止", "✗", "ERROR")
            return 1
    else:
        log("跳過發送邀請", "→")
        if not invite_results.exists():
            log(f"找不到邀請結果文件: {invite_results}", "✗", "ERROR")
            log("請先執行邀請步驟，或移除 --skip-invitations 參數", "!", "ERROR")
            return 1

    # ── 步驟 3：提取被邀請郵箱 + 子號登入 ───────────────────────
    log("", "=")
    log("步驟 3/4：子號登入", "=")
    log("", "=")

    count = extract_invited_emails(invite_results, invitees_txt)
    if count == 0:
        log("沒有被邀請的郵箱，跳過子號登入", "!")
    else:
        cmd = [
            python_exe, "codex_protocol_login.py",
            "--json", str(invitees_txt),
            "--out-dir", str(invitees_dir),
            "--concurrency", str(args.concurrency),
            "--oidc-sso-url", args.oidc_sso_url,
            "--oidc-sso-admin-token", args.oidc_sso_admin_token,
            "--oidc-sso-invite-code", args.oidc_sso_invite_code,
        ]
        if args.proxy:
            cmd.extend(["--proxy", args.proxy])

        if not run_command(cmd, "子號登入"):
            log("子號登入失敗，繼續執行激活步驟", "!", "WARN")

    # ── 步驟 4：子號激活 ─────────────────────────────────────────
    if not args.skip_activation:
        log("", "=")
        log("步驟 4/4：子號激活", "=")
        log("", "=")

        if not invitees_dir.exists() or not list(invitees_dir.glob("*.json")):
            log("沒有子號憑證，跳過激活", "!")
        else:
            cmd = [
                python_exe, "codex_activation_batch.py",
                "--auth-dir", str(invitees_dir),
                "--concurrency", str(args.concurrency),
                "--save-back",
            ]
            if args.proxy:
                cmd.extend(["--proxy", args.proxy])

            if not run_command(cmd, "子號激活"):
                log("子號激活失敗", "!", "WARN")
    else:
        log("跳過子號激活", "→")

    # ── 完成 ─────────────────────────────────────────────────────
    log("", "=")
    log("流程完成", "=")
    log("=" * 60, "=")
    log(f"母號憑證: {seeds_dir}")
    log(f"邀請結果: {invite_results}")
    log(f"子號憑證: {invitees_dir}")
    log("=" * 60, "=")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[!] 用戶取消。")
        sys.exit(130)
