# B282：A1＋跨频专家细化，两种模型

本包直接复用 **B280 A1**。不从头重训 A1，不覆盖 B280，不读取或重建旧 WVD 缓存。包含训练、断点续跑、校准、审计、37 点 Pd 曲线、独立 IQ 推理及测试。

## 三组训练、四条曲线

|标记|结构与训练|
|---|---|
|A1 frozen|原 B280 A1 权重冻结，作为参考，不训练|
|control|A1 同预算继续训练，无新模块|
|unguided|A1＋跨频专家细化；路由的一致性输入通道固定为零|
|guided|A1＋完整一致性引导跨频专家细化；路由读取真实前端一致性图|

两组新模型的结构、参数量、随机初始化相同，仅一致性输入不同。每组增加 **20,214** 参数，约为 A1 的 0.14%。保留全部八个原生 SimAM，损失只有 CE，不使用 TFCG、Tail、phase-ARS 或教师蒸馏。

三组训练均从相同 A1 权重出发，使用相同样本、批次、轮数和学习率。为降低分布漂移，冻结原前端及原 BN 的仿射参数和运行统计，其余 CNN/FC 可训练。新模块初始残差为零；启动检查会核对它们的初始 logits 与 A1 一致。初始一致不保证训练后 Pd 不下降。

## AutoDL 最短运行方法

将 **B282_A1_CFEXPERT_V1.zip** 上传到：

`/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/`

在 AutoDL 终端执行：

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1
unzip -n B282_A1_CFEXPERT_V1.zip
bash B282_A1_CFEXPERT_V1/start_on_autodl.sh
tail -F codex_b282_cfexpert.log
```

后台启动器直接使用 `conda run -n mpdnet-r10`，无需 `conda activate` 或 `conda init`。启动后用 Ctrl+C 退出 `tail` 只会停止看日志。不要按 Ctrl+C 中断前台训练。SSH/本地网络断开后，已由 nohup 启动的服务器进程可继续运行；服务器关机、容器被回收不在此保证范围内。

默认自动串行执行三组训练，再校准、审计、画图，不需要逐组启动。使用既有 `codex_b271_night.lock` 避免与其他已接入该锁的实验争抢 GPU；这不能检测未使用此锁的任意进程。

## 默认预算

- TRAIN：16,000 条，从冻结 30,000 条 TRAIN 中按类别/家族分层取样；VAL：原完整 5,000 条。
- 每组继续训练 6 epoch，batch32，原 CNN/FC lr=1e-5，新模块 lr=3e-4，Adam、weight decay1e-4。
- 中等规模评分：H0 CAL300,000、独立 H0 AUDIT200,000、512 个 H1 场景×37 个 SCR 点（-24..12 dB）。
- 默认只画标称 Pfa=1e-4。不同方法各用自己的 H0 CAL 阈值，并同时给出实际审计 Pfa 与 Wilson95%区间。
- 方案和检查没有在本地 CUDA 或用户真实 IQ 上运行；AutoDL 启动会实际执行每组 batch32 的三步优化显存检查。

这次不默认运行3M/1M的大评分。实际耗时依赖服务器速度；日志会提供每轮耗时和评分剩余时间。

## 必须保留的旧文件

默认 A1 来源：`output_b280_full_ablation_v1/`，需要：

```text
A1/best.pt
A1/training_contract.json
pd_scr_full/protocol_frozen.json
pd_scr_full/progress.json
```

以及冻结 IQ 数据目录：`SIM_R10_IQ512_TRAIN30000_VAL5000_SEED20261009_V1/`。

如旧评分数组仍在，脚本会在同设备类型、同 PyTorch 版本、同 batch 的前提下校验文件和 H0/H1 数值前缀，复用 A1 列对应的配对场景前缀。缺失的数组会重新计算 A1 分数。**中等规模会用中等规模 CAL 为 A1 重新定阈值，不直接叠加 B280 大规模曲线。**

新组始终重新计算分数；不会把旧结果改名作为新组。源权重、训练数据和旧评分数组只读。

来源目录不同可指定：

```bash
bash B282_A1_CFEXPERT_V1/start_on_autodl.sh \
  --source-run /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/你的B280输出目录
```

若历史分数数值前缀核对失败，先保存日志检查原因；可以从首次运行就加 `--recompute-a1-scores` 强制重新计算 A1。该设置会成为运行身份的一部分，不能在同一输出目录的中途随意切换。

## 输出和恢复

```text
output_b282_a1_cfexpert_v1/
  source_A1_full_VAL_replay.json
  source_A1_numeric_probe.json
  optimizer_canary.json
  control/{best.pt,last_epoch.pt,training_contract.json,train_val_history.csv}
  unguided/{best.pt,last_epoch.pt,training_contract.json,train_val_history.csv}
  guided/{best.pt,last_epoch.pt,training_contract.json,train_val_history.csv}
  pd_scr_medium/
    b282_metrics.csv
    b282_comparisons.csv
    b282_ablation_table.csv
    b282_curves.csv
    b282_report.json
    figures/b282_pd_scr_pfa_1e-04.pdf
```

**选模型仅使用 TRAIN/VAL**：在 VAL CE 不超过原 A1 CE+0.01 的条件下最大化 VAL pAUC@0.01，CE 作同分决胜，epoch0可选。pAUC@0.01是有限 VAL 的代理指标，不是 Pfa=1e-4 的验证结果。CAL/AUDIT/DEV 不参与梯度或最佳 epoch 选择。

若选中 epoch0，脚本明确输出 `EPOCH0_SELECTED__NO_NEW_MODULE_GAIN_CLAIM`，不能说新模块带来增益。选中后也要检查实际 Pd、D80/D90 和 Pfa。

程序异常退出后，确认后台进程已结束，重新执行同一启动命令即可。按 epoch 原子保存训练状态；评分按 H0 chunk、H1 SCR 点提交。已经完成且校验一致的组会跳过。参数、源文件或数据变化时会停止，要求新输出目录，避免混写。

## 中等规模通过后，只扩大评分

已有三组权重可直接用于完整评分，无需重训：

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1
bash B282_A1_CFEXPERT_V1/start_on_autodl.sh --stage score --eval-size full
tail -F codex_b282_cfexpert.log
```

完整评分：CAL3,000,000、AUDIT1,000,000、H1=1024×37，同时画 Pfa=1e-4 和1e-5，写入 `pd_scr_full/`，保留 `pd_scr_medium/`。

如果明确要把继续训练也扩大到30,000条，用新的输出目录，避免与16,000条版本混合：

```bash
bash B282_A1_CFEXPERT_V1/start_on_autodl.sh \
  --train-limit 30000 --out-dir /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/output_b282_a1_cfexpert_train30k_v1
```

## 独立 IQ 推理

输入为 `complex64`、形状 N×512 的 `.npy`。输出连续分数；若需要判决，提供匹配校准所得的阈值，不能默认0为低虚警阈值。

```bash
/root/miniconda3/bin/conda run --no-capture-output -n mpdnet-r10 \
  python B282_A1_CFEXPERT_V1/b282_infer.py \
  --checkpoint output_b282_a1_cfexpert_v1/guided/best.pt \
  --iq your_iq_complex64.npy --out your_scores.npz
```

## 文献来源与适配范围

借鉴 FAME-Net 的 CF-MoE/MG-Routing：Du et al., IEEE TGRS, 2026, DOI **10.1109/TGRS.2026.3694686**。本包从论文机制重新实现适配，没有使用作者仓库代码，不是红外论文整网复现。具体差异见 `METHOD_DESIGN.md`；原文应在论文中引用。

这轮中等规模结果是已多次查看的 SIM-R10 DEV 探索结果，不能替代独立 TEST、实测海杂波泛化或多种子统计。没有预先保证超过 A1 或左移1dB。

## 本地功能测试

```bash
python -m unittest discover -s tests -v
```

测试使用合成/生成 IQ 和缩小的样本夹具，检查真实网络前后向、梯度、初始化、源文件校验、恢复、推理、评分及图形。CPU测试不代表RTX3080Ti上的显存/速度验证。
