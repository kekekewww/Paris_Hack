# 依賴漏洞與一致性查核

查核日期：2026-10-17（臺灣）。本次實際執行結果：**後端 33 個 runtime 套件已查詢漏洞庫，未發現已知漏洞且無跳過項目；npm audit 為 0 已知漏洞；Python 依賴一致性檢查通過。** 三項檢查的能力不同，不能彼此替代。

## 範圍與工具隔離

- 產品環境：Windows、Python 3.12.14、npm 11.4.2。
- 先檢查既有工具：未找到 `pip-audit`，產品 `.venv` 執行 `python -m pip_audit --version` 也顯示模組不存在。
- 另建 `.local/audit-venv` 並從官方 PyPI 安裝 `pip-audit==2.10.1`。掃描器及其依賴只安裝於此隔離環境，沒有安裝或升級產品 `.venv` 的套件。
- 從 `backend/requirements.txt` 的 7 個 runtime 根套件，以產品環境 `importlib.metadata` 及環境 marker 解析實際依賴閉包，共 33 個套件，逐一與 `backend/constraints.txt` 比較，版本完全一致。
- constraints 另外包含的 `pytest`、`iniconfig`、`pluggy`、`pygments` 為測試工具，不在本次後端 runtime 漏洞掃描範圍。掃描器自身、Python 標準函式庫與作業系統亦不在該範圍。

精確輸入已保存為 [runtime 鎖定清單](evidence/python-runtime-requirements-2026-10-17.txt)，其來源與解析結果保存於 [掃描範圍 JSON](evidence/dependency-audit-scope-2026-10-17.json)。本次沒有執行 `--fix`，沒有更動任何產品套件或 constraints。

## 實際執行命令

工作目錄皆為專案根目錄 `D:\Developing\Paris`。

```powershell
.venv\Scripts\python.exe -m pip_audit --version
.venv\Scripts\python.exe -m venv .local\audit-venv
.local\audit-venv\Scripts\python.exe -m pip install --disable-pip-version-check --no-cache-dir --index-url https://pypi.org/simple pip-audit==2.10.1
.local\audit-venv\Scripts\python.exe -m pip_audit --version
.local\audit-venv\Scripts\python.exe -m pip_audit -r .local\audit-runtime-requirements.txt --no-deps --disable-pip --strict --vulnerability-service pypi --format json --output .local\pip-audit-runtime.json --cache-dir .local\audit-cache --progress-spinner off --timeout 20
.venv\Scripts\python.exe -m pip check
npm.cmd audit --json --registry=https://registry.npmjs.org > .local\npm-audit.json
```

`.local/audit-runtime-requirements.txt` 是上述 metadata 閉包產出的 33 個完整版本 pin，已原樣保存至 docs/evidence。重現掃描時可將保存清單複製回 `.local`，或將 `-r` 改指向保存清單。`--no-deps --disable-pip` 只略過再次解析依賴，不會略過漏洞庫查詢；版本閉包與 constraints 的一致性已另外驗證。

初次掃描程序返回 1、未輸出文字也未產生結果檔，因此當時沒有算作通過。加上 `-v` 與日誌後成功查詢全部套件；再以原始、沒有管線的命令重跑，直接取得退出碼 0 與下列結果。沒有忽略任何 advisory，也沒有使用 dry-run。

## 結果與證據

| 檢查 | 實際結果 | 證明範圍 |
|---|---|---|
| `pip-audit 2.10.1`／PyPI 漏洞服務 | 退出碼 0；`No known vulnerabilities found`；33/33 套件，0 漏洞，0 skipped | 掃描當下資料庫已知的 Python 套件版本漏洞 |
| `npm audit --json` | 退出碼 0；info／low／moderate／high／critical 全為 0 | npm lock 所列依賴的資料庫已知漏洞；metadata total 為 88 |
| 產品 `.venv` 的 `pip check` | 退出碼 0；`No broken requirements found.` | 已安裝套件的相依版本一致性，不是漏洞掃描 |
| runtime 閉包與 constraints | 33 個版本全部一致；掃描結果完整覆蓋，無 skip | 未漏掃當前環境下的 runtime 相依套件 |

保存的原始證據：

- [pip-audit 結果 JSON](evidence/pip-audit-runtime-2026-10-17.json)
- [npm audit 結果 JSON](evidence/npm-audit-2026-10-17.json)
- [覆蓋率及輸入未變更核對 JSON](evidence/dependency-audit-verification-2026-10-17.json)

查核前後的輸入 SHA256 相同：

| 輸入 | SHA256 |
|---|---|
| `backend/requirements.txt` | `2eed755ebe77f68ddb9a1b4d5dbf87647141d49a3a854719cacf8939e67acb2a` |
| `backend/constraints.txt` | `f3c3f8b84fc5866f794145d4232211c811bdaef912e6f2ee1162c1c8d52534b8` |
| `package-lock.json` | `3a2cef9360fe41bc822ea295ccbf0eeff9eca59fe54e3dff75edb2e2e09f30f0` |

## 限制與後續

結果表示掃描當下沒有資料庫已知漏洞，不保證不存在未公開漏洞、供應鏈問題或產品程式漏洞。pip-audit 提示完整 pin 尚未附下載檔案 hash；本次驗證版本閉包，但不宣稱已完成 wheel 來源完整性或可重現建置查核。依賴改版、部署平台改變或重新展示前應重跑掃描。

本次不需要依 advisory 修補套件；正式容器映像與作業系統漏洞掃描仍需在實際可建置的部署環境另外執行。本查核沒有執行 OCR、呼叫 LLM 或更動帳戶。

工具能力及退出碼依 [pip-audit 官方說明](https://pypi.org/project/pip-audit/)；Python 依賴一致性檢查依 [pip check 官方說明](https://pip.pypa.io/en/stable/cli/pip_check/)。
