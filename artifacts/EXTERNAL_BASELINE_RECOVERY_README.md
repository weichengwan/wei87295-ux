# 外部 baseline 恢复与核对（2026-10-16）

此工具只收集服务器已有文件，不训练、不推理、不更改历史文件。生成的 ZIP 包包含代码及小型报告，不包含模型权重、原始 IQ、NPY 或 HDF5 内容。权重与大数组仅记录路径、大小和修改时间。每个文件限制 2 MiB，总收集量限制 80 MiB；符号链接仅记录，不跟随。

运行：

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1
python /tmp/collect_external_baselines.py --root "$PWD"
```

终端会给出 `EXTERNAL_BASELINE_MINI_时间戳.zip` 路径。将该文件上传到对话，权重先留在服务器。脚本还会收集 B283 日志最后 25 行，以便据实际速度更新耗时估计。

## 已核实的文献身份

- CVHSTNet：*Overcoming Data Scarcity in Maritime Radar Target Detection via a Complex-Valued Hybrid Spatiotemporal Network*，IEEE Geoscience and Remote Sensing Letters，vol.22，2025，article3503405，DOI:10.1109/LGRS.2025.3557817。输入是复数 STFT，模型是复数 CNN 与复数 BiLSTM。原文关注 IPIX 小样本场景，主要展示 Pfa=1e-3 的结果；历史 SIM 适配曲线并非原论文性能复现。
- FARC-CAT：*False Alarm Rate-Controllable Maritime Target Detection via Cross-Attention Transformer Network*，IEEE Sensors Letters，vol.10，no.7，2026，article6006304，DOI:10.1109/LSENS.2026.3696409。幅度和 STFT 两个编码器、双向交叉注意力、门控融合、含可学习阈值的虚警约束损失。
- FSST+SimAM-ResNet18：上传源码注释指向 YANG Haida 等的 *Sea-Surface Targets Detection Method Based on Improved Residual Neural Network*，Modern Defence Technology，2026，54(4):151–158。此条仅来自历史实现的注释，尚需原文核验。FSST 与 STFT 为不同变换，历史 B238 修正 FSST 与 B242 STFT 消融不可互相更名。

## 已从用户上传的文件确认

B270_ALL_PY.tar.gz 中找回 9 个 FSST 相关脚本和 6 个 FARC-CAT 脚本，包含变换、模型、训练、H0 校准和 H1 评分。它们是项目内依据论文的重建与适配，不能称为作者官方源码；现有这些脚本主要对应实测 MTDSP 协议，需进一步找回 SIM-R10 适配层。

CVHSTNet 的完整 SIM 实现未在当前已上传源码压缩包中找到。旧终端记录明确出现 `B241_CVHSTNET_2025_SIM_R10_V1/b241_paired_score.py`，以及 B241/B241R 训练和评分输出目录，服务器现存状态待收集确认。

## 需要核对的历史目录

- `B238_FSST_CORRECTED_PAIRED_V1`、`output_sim_r10_b238_fsst_corrected_train_v1`、`output_sim_r10_b238_fsst_corrected_paired_v1`
- `B242_STFT_SIMAM_RESNET18_V1`、`output_sim_r10_b242_stft_simam_train_v1`、`output_sim_r10_b242_stft_simam_paired_v1`
- `B241_CVHSTNET_2025_SIM_R10_V1`、`B241R_VALSTOP_DIAGNOSTIC_V1`、`output_sim_r10_b241_cvhstnet_train_v1`、`output_sim_r10_b241_cvhstnet_paired_v1`、`output_sim_r10_b241r_valbest_train_v1`
- `SIM_R10_B225_REAL_FOUR_DL_TRAIN_V1`、`output_sim_r10_b225_real_four_dl_train_v1`
- `SIM_R10_STAGE_B223_EXTERNAL_BASELINES_V1`、`output_sim_r10_b223_external_baselines_v1`
- `SIM_R10_B224_NIGHT_EXTERNALS_REFSTYLE_V1`、`output_sim_r10_b224_reference_style_v1`
- `SIM_R10_B226_MATCHED_PDSCR_V1`、`output_sim_r10_b226_matched_pdscr_v1`
- 顶层 `r10_2025_mtdsp_*fsst*` 与 `r10_2025_mtdsp_*farccat*` 文件及同名输出目录。

目录名来自旧终端清单，不代表已经验证服务器当前仍有文件。B223 的 adapter template 不能替代完整的已训练模型证据。

## 复用顺序

1. 从训练配置和 VAL 选择记录确定方法身份、数据、预算与权重；不根据 H1 曲线挑选检查点。
2. 核对训练与评估场景是否隔离、IQ 长度、变换设置、评分单位和聚合方法。
3. 对齐 B283 的固定场景种子、H0 CAL/AUDIT、37点 SCR 与两个 Pfa。
4. 权重和协议均匹配时复用现有分数；仅分数缺失或协议不同则重评分；权重缺失或训练协议明显不同才讨论重训。
5. 原文阈值规则与统一 H0 校准阈值若不同，明确列明适配；保留 FARC-CAT 的原生阈值结果供核对。

不能直接将旧实测 MTDSP LOAO 的结果表与当前 SIM-R10 DEV 曲线合并。当前多次查看的 DEV 不等于独立最终 TEST。
