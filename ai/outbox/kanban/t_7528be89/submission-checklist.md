# t_7528be89 submission checklist

## Scoped add command

```bash
git add -- \
  backend/app/domains/business_analysis/services/inventory_sales_production/sql_plan.py \
  tests/unit/business_analysis/test_inventory_sales_production_sql_plan.py \
  ai/outbox/kanban/t_7528be89
```

## Required pre-commit gates

- `git diff --cached --name-status`
- `git diff --cached --check`
- Confirm no `.env` / credentials / production connection strings.
- Confirm no push / deploy.

## Commit message

```text
[verified] 修复产销存M5业务规则脱敏门禁
```
