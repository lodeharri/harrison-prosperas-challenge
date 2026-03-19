---
name: symbol-connectivity-check
description: Automated verification that new code is actually called within the application logic.
---

# Instructions
1. **Identify Símbolo**: Find the name of the function/feature just implemented.
2. **Scan Codebase**: Execute `grep -r "<symbol_name>" . --exclude-dir=node_modules`.
3. **Analyze Results**:
    - **Count == 1**: The function is "loose" (uncalled). FAIL.
    - **Count > 1**: The function is integrated. SUCCESS.
4. **Report**: Document the call-site file and line number in the technical summary.