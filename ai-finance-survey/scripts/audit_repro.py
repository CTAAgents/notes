# -*- coding: utf-8 -*-
"""复现状态审计：查询公开基准/工具的 GitHub 仓库可见信息。
记录 stars、许可、最近推送、是否归档等, 用于复现状态核验表。
只记录接口真实返回, 未编造。"""
import json
import time

import requests

OUT = r"d:\Finance\AI金融交易综述\outputs\repro_audit.json"
H = {"User-Agent": "ai-fin-trading-survey/1.0",
     "Accept": "application/vnd.github+json"}

REPOS = [
    "microsoft/qlib",
    "AI4Finance-Foundation/FinRL",
    "AI4Finance-Foundation/FinRL-Meta",
    "AI4Finance-Foundation/FinGPT",
    "hudson-and-thames/mlfinlab",
    "esvhd/pypbo",
    "mementum/backtrader",
    "quantopian/alphalens",
    "quantopian/zipline",
    "polakowo/vectorbt",
    "quantopian/empyrical",
    "quantopian/pyfolio",
    "abides-sim/abides",
    "stefan-jansen/machine-learning-for-trading",
]


def main():
    res = {}
    for full in REPOS:
        try:
            r = requests.get(f"https://api.github.com/repos/{full}", headers=H, timeout=30)
            if r.status_code != 200:
                res[full] = {"error": f"HTTP {r.status_code}"}
                print(f"[ERR] {full}: HTTP {r.status_code}")
                time.sleep(1)
                continue
            d = r.json()
            lic = (d.get("license") or {}).get("spdx_id")
            res[full] = {
                "full_name": d.get("full_name"),
                "terse": d.get("description"),
                "stars": d.get("stargazers_count"),
                "forks": d.get("forks_count"),
                "open_issues": d.get("open_issues_count"),
                "license": lic,
                "created_at": d.get("created_at"),
                "pushed_at": d.get("pushed_at"),
                "archived": d.get("archived"),
                "has_wiki": d.get("has_wiki"),
                "default_branch": d.get("default_branch"),
            }
            print(f"[OK ] {full:45s} stars={d.get('stargazers_count'):<7} "
                  f"lic={lic:<12} pushed={str(d.get('pushed_at'))[:10]} arch={d.get('archived')}")
        except Exception as ex:
            res[full] = {"error": str(ex)}
            print(f"[ERR] {full}: {ex}")
        time.sleep(1)

    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n已保存: {OUT}")


if __name__ == "__main__":
    main()
