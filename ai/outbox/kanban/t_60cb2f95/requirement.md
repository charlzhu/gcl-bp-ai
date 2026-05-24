# NQE-SQL-MAIN-14 需求说明

## 目标

1. 实现统一 SQL Agent 所需的物流元数据同步能力
2. 补齐 nqe_metadata_sync 模块
3. 为 NQE SQL Agent Graph 的物流 auto-context 提供上下文包
4. 解锁此前失败的 2 个 auto-context 测试
5. 为 NQE-SQL-MAIN-15 提供前置能力

## 实现方式

从恢复工作树 .worktrees/nqe-sql-main-6-metadata-migrations/ 回填：

- NqeMetadataSyncBuilder：从受控 YAML catalog 构建元数据 bundle
- build_nqe_context_package_from_bundle：将 bundle 转为 Graph 可用的上下文包（ready + allowed_tables + table_columns）

Catalog 源目录：backend/app/domains/logistics/config/nl2sql_catalog/
