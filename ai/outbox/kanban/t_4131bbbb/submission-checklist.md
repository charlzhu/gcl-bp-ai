# t_4131bbbb submission checklist

## Branch

- Required branch: `feature/isp-m5-inventory-nl2sql-integration`
- Must re-check with `git branch --show-current` immediately before commit.

## Scoped add command

Do not use `git add -A` or `git add .`.

Use explicit staging only:

```bash
git add \
  backend/app/domains/business_analysis/services/inventory_sales_production/m5_shadow_compare.py \
  scripts/dev/run_inventory_sales_production_m5_shadow_compare.py \
  tests/unit/business_analysis/test_inventory_sales_production_m5_shadow_compare.py \
  ai/outbox/kanban/t_3ca95bf9 \
  ai/outbox/kanban/t_45ab3a93 \
  ai/outbox/kanban/t_4131bbbb
```

## Required pre-commit checks

- `git diff --cached --name-only` must show only the scoped paths above.
- `git diff --cached --check` must pass.
- `frontend/tsconfig.tsbuildinfo` must not be staged.
- Do not stage `ai/outbox/kanban/t_d76060c2/**` or `ai/outbox/kanban/t_87762691/**` in this final commit; they are historical failed process evidence and not the final pass basis.

## Commit message

`[verified] 收口产销存M5影子对比验收材料`
