# M9.1 RED / GREEN 记录

## RED

历史 live provider shadow gate 中 `m9_success_yearly_mw_breakdown` 暴露两个失败码：

1. `sqlplan_join_required_for_multi_table_plan`
2. `sqlplan_missing_default_time_filter::2023_2026`

此外，旧 worker 后续因 preflight 分支/dirty 工作区不满足任务硬条件而反复 blocked，未能继续进入验证收口。

## GREEN

本轮重新执行验证矩阵：

- provider smoke：PASS。
- catalog reindex：PASS，indexed_count=127。
- M9 focused tests：PASS，26 passed。
- catalog focused tests：PASS，20 passed。
- broader NL2SQL tests：PASS，190 passed。
- compile：PASS。
- live provider shadow gate：PASS，rc=0，total=3，success=2，validation_failed=1，expected_status_mismatch_count=0。
- static scan：PASS，高风险 0。
- independent review：PASS。

## 结论

M9.1 的 live provider yearly_mw_breakdown 稳定性问题已通过功能门禁验证；剩余风险是共享工作区当前仍混有非 M9.1 dirty 文件，提交/合并前需要隔离处理。
