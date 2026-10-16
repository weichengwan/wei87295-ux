# B283：TFSE 与 CGCR 全量递进消融

## 统一名称

|缩写|中文名称|英文名称|对应实际实现|
|---|---|---|---|
|TFSE|时频协同增强模块|Time-Frequency Synergistic Enhancement|B280 A1 已有联合多尺度 SPWVD 与空间门控前端|
|CGCR|一致性引导跨频细化模块|Consistency-Guided Cross-Frequency Refinement|B282 guided 已有的一致性引导跨频专家细化|

本轮统一描述性名称、扩大评分规模和调整图式，**不改变已有模型公式或权重，不重新训练**。TFSE 内部仍使用既有 SPWVD 离散实现；CGCR 应说明借鉴 FAME-Net（IEEE TGRS2026，DOI10.1109/TGRS.2026.3694686）的 CF-MoE/MG-Routing 及本项目改造。名称不构成性能或原创性证明。

## 直接运行

将 **B283_TFSE_CGCR_FULL_V1.zip** 上传到：

`/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/`

执行：

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1
unzip -n B283_TFSE_CGCR_FULL_V1.zip
bash B283_TFSE_CGCR_FULL_V1/start_on_autodl.sh
tail -F codex_b283_full_ablation.log
```

启动器直接调用 `conda run -n mpdnet-r10`，无需手动激活环境。后台运行，SSH断开后可继续。Ctrl+C退出tail只停止查看日志。服务器关机或进程被终止后，需要重新运行同一启动命令恢复。

## 五组现有模型

|表格顺序|模型来源|TFSE|跨频细化|继续训练|
|---|---|---|---|---|
|1|B280 A0 原 ADN|无|无|无新增微调|
|2|B280 A1 frozen|有|无|无新增微调|
|3|B282 control|有|无|已有同预算微调|
|4|B282 unguided|有|不读取一致性的基础版|已有同预算微调|
|5|B282 guided 最终候选|有|完整CGCR|已有同预算微调|

这是**递进消融，保留同预算继续训练对照**。B280 的 A0/A1 是原来的配对训练；B282 三组是由 A1 出发的同预算微调。本次直接使用这些权重，不将它们改称“全部从头训练且预算相同”。训练样本数、训练轮数、选中epoch会写入消融表。

表格不能解释为完整2×2消融，因为当前没有“去掉TFSE但保留完整CGCR”的已训练模型。若要补那一组，需要另外定义一致性输入并训练，当前包不会虚构或自动补训。

## 全量评分规模

- H0 CAL：3,000,000。
- 独立 H0 AUDIT：1,000,000。
- H1：1024个相同场景，SCR为-24到12dB，共37点。
- 标称 Pfa：**1e-4 与1e-5**，每个模型各用自己的全量CAL阈值。
- 同时输出实际审计Pfa、95%区间、D80、D90、Pd@0/6/9/12dB及对比表。

此处扩大的是**评价规模**。B282三组仍使用之前已经训练出的权重，原先16,000条训练样本的微调记录保留，不会改写为30,000条训练。

全量DEV已多次被查看，扩大样本量不自动使其成为独立最终TEST。

## 自动复用哪些内容

1. 复用B280原ADN和A1权重。
2. 复用B282三组权重，保留各自VAL选择的检查点。
3. 如B280完整原始分数数组仍在，校验后复用ADN、A1两列。
4. 如B282已做过完整评分，优先复用完整分数；否则复用已经完成的中等规模前缀（CAL30万、AUDIT20万、H1每点前512场景）。
5. 只推理缺失的模型/场景，不重算已核验的分数。完全缓存的chunk不会生成IQ或运行网络。

所有复用受检查点SHA、训练配置、场景协议、生成器、设备类型、PyTorch版本、batch32、文件SHA和数值抽查约束。数值抽查覆盖首尾原始批次及多个H1 SCR点，但不等于对全数组重新推理。

旧分数数组缺失时，可从保留的模型重新评分；旧权重缺失时会明确报错，**不会自动重训**。未完成的旧评分目录保留并跳过，B283自身已有评分会按提交进度恢复。

## 必须保留的文件

默认路径为：

```text
output_b280_full_ablation_v1/
  A0/best.pt
  A0/training_contract.json
  A1/best.pt
  A1/training_contract.json
  pd_scr_full/protocol_frozen.json
  pd_scr_full/progress.json

output_b282_a1_cfexpert_v1/
  control/best.pt
  control/training_contract.json
  unguided/best.pt
  unguided/training_contract.json
  guided/best.pt
  guided/training_contract.json

SIM_R10_IQ512_TRAIN30000_VAL5000_SEED20261009_V1/
```

评分数组可选；保留它们会减少推理时间。B282的原始代码包不必在服务器上保留，本包附有未经修改的Python实现来识别权重，不修改旧代码的指纹。

目录名称不同可指定：

```bash
bash B283_TFSE_CGCR_FULL_V1/start_on_autodl.sh \
  --b280-run /你的B280输出目录 \
  --b282-run /你的B282输出目录
```

## 绘图修改

- 最终候选图例为 **ADN + TFSE + CGCR (Ours)**。
- 最终候选为**黑色实线、空心倒三角**；三角形大小、间隔和边框沿用之前设置。
- Pd图上方分别标明 **Nominal Pfa=10^-4** 或 **Nominal Pfa=10^-5**，PDF中采用数学公式排版。
- 保留原A1、control、无引导版三条曲线的颜色、线型、圆形标记与坐标轴设置；横轴仍为SCR(dB)，纵轴仍为Pd。
- 原ADN作为新增第五条曲线追加在图例后，避免改变原三条对照的颜色编号。
- 不平滑、不水平移动、不修改真实Pd值。

## 输出

```text
output_b283_tfse_cgcr_full_v1/
  run_manifest.json
  cache_numeric_probe.json
  pd_scr_full/
    progress.json
    protocol_frozen.json
    h0_cal_scores.npy
    h0_audit_scores.npy
    dev_h1_scores.npy
    b283_metrics.csv
    b283_comparisons.csv
    b283_ablation_table.csv
    b283_ablation_table.md
    b283_ablation_table_pfa_1e-04.pdf
    b283_ablation_table_pfa_1e-05.pdf
    b283_report.json
    b283_curves.csv
    figures/b283_pd_scr_pfa_1e-04.pdf
    figures/b283_pd_scr_pfa_1e-05.pdf
```

输出分数数组约154MiB，启动要求至少512MiB空闲。不生成WVD训练缓存或新的模型权重。全量推理仍可能较久，日志按阶段提供速度和预计剩余时间。

异常退出后，确认原进程已结束，再运行同一启动命令。参数、源权重或被复用的缓存发生变化时会停止，避免把不同来源混在同一结果中；此时应保存旧结果并另设 `--out-dir`。

## 可选操作

仅检查权重和缓存：

```bash
bash B283_TFSE_CGCR_FULL_V1/start_on_autodl.sh --stage preflight
```

所有评分完成后，只重新生成图表，不运行网络：

```bash
/root/miniconda3/bin/conda run --no-capture-output -n mpdnet-r10 \
  bash B283_TFSE_CGCR_FULL_V1/run_b283.sh --stage report
```

如果首次运行就决定全部重算分数，可加 `--recompute-scores`；这只重算推理，不训练。运行中不要切换这个选项。缓存数值核对失败时先保留日志检查来源，不自动忽略不匹配。

## 测试范围

```bash
python -m unittest discover -s tests -v
```

测试使用生成IQ、合成检查点和合成评分夹具，验证真实网络加载、与原实现一致的预测、选择性缓存复用、无优化器执行、断点恢复、双Pfa图式及训练预算记录。没有在本地运行用户真实雷达权重或CUDA实验。真实性能以AutoDL输出为准。
