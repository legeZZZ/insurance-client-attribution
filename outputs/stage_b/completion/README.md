# 阶段 B 验收证据

T07–T16已完成支持设计内的实现、入口与验收。最终完整回归161/161，40.475秒；新增17项测试，16个实际CLI请求。

- `requests/`：可直接交给 tools/run_causal_pipeline.py 的JSON输入；同名顶层JSON为实际输出。
- `cli_summary.json`：所有运行状态，包括GCM拒绝与序贯停止。
- `full_tests.log`、`targeted_tests.log`、`static.log`、`dependencies.json`：程序验收。
- `statistical_matrix.json`：六种关联配置，每配置100次；以及五方法A/A、A/B初始100次。
- `randomized_1000.json`：五方法A/A、A/B各1000次，保留全部种子。
- `observational_1000.json`：DiD/SCM/BSTS各1000次。
- `did_10000.json`：连续同种子序列的DiD扩展核验，含前1000次，不应将两文件相加计数。
- `extensions_matrix.json`：100次GCM、100次森林HTE、1000次有限检查点序贯A/A。
- `manifest.json`：源码、文档、依赖和证据摘要。

统计区间和模型适用性见代码包《因果流水线接口说明.md》；完整阶段状态见交付包根目录《阶段实施记录.md》。此处不将阶段B验收表述为阶段C/D闭环或阶段E跨业务全链路盲测已完成。
