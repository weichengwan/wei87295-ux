# B286: ADN + LCBR，先做独立增益验证

本包将 B284 未获得独立增益的 CGCR 换成 2026 年 TIP 论文中广播注意力机制的两种适配。
它是新的实验候选，尚无 AutoDL 的 Pd 结果，不预先认定为已成立的第二创新点。

引用：Qian Wang et al., **Broadcast-Gated Attention With Identity Adaptive Integration for Efficient Image Super-Resolution**, IEEE Transactions on Image Processing, vol.35, pp.1408–1422,2026.
DOI: <https://doi.org/10.1109/TIP.2026.3657640>。作者代码：<https://github.com/bbbolt/BGAI>。
你已上传该原文，不需要重新提供 PDF。

## 实验三组

| 曲线 | 输入与网络 | 训练 |
|---|---|---|
| ADN (matched control, B284) | WVD → 原始 ADN 的 ACB/ResNet18 与8个 SimAM → 分类 | 复用 B284 ADN 权重和对应分数，无重训 |
| ADN + broadcast attention | 原 ADN 的完整 layer2 之后，增加 BGMSA 广播细化 | 从相同 B280 A0 起点，匹配 B284 的续训预算 |
| ADN + LCBR (proposed) | 与上一行相同，增加局部背景对比对广播门控的调节 | 同样的起点、数据、优化器、续训预算 |

**LCBR：局部对比广播细化，Local-Contrast Broadcast Refinement。**
广播机制引用原文；局部背景对比参与广播门控是本实验的适配改动。不是给原模块换名。
本轮仅看模块能否在 WVD ADN 上获得独立增益，所有组均不使用 TFSE、CGCR、TFCG、Tail 或 phase-ARS。
全部保留 ADN 原有8个 SimAM；新模块接在 layer2 完整残差块之后、layer3 之前，不插进原有冻结 BN 内。
“原始 ADN”在本项目中指保持该论文网络结构的本地复现；不意味着与作者原始训练数据/预处理/结果完全等价。

## 数据与训练预算

复用冻结 IQ512 的30k TRAIN/5k VAL 数据库、现有完整 WVD TRAIN/VAL 缓存；从中选取与 B284 完全相同的16k TRAIN 和5k VAL。
仅两组各续训6个 epoch，batch32。骨干学习率1e-5，新模块3e-4，Adam，weight_decay1e-4，CE only。
原 BN 的仿射参数和运行统计冻结，其余 CNN/FC 与新模块训练。新模块零残差起步，初始 logits 与 B280 A0 相同。
最大化 VAL pAUC@0.01，要求 VAL CE 不超过同一原始 A0 的 CE+0.01，以 CE 打破平局，epoch0允许被选中。
该 VAL pAUC 是选模代理指标，不能证明在1e-4/1e-5处已有提升。

默认中规模：H0 CAL300,000、独立 H0 AUDIT200,000、H1每个 SCR512个场景、37点 SCR=-24…+12dB，只画 Pfa=1e-4。
所有组使用同一批场景，阈值各自由 CAL 确定；实际虚警及其95%区间由 AUDIT 独立统计。
大规模评估仍支持 CAL3M/AUDIT1M/H1=1024×37以及1e-4、1e-5，但不会自动接着跑。
现有 DEV 多次曝光，这些结果用于筛选，不作为独立最终测试。

## 放置及运行

将 ZIP 解压在 `/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1` 下，得到本包的独立目录。

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1
unzip -n B286_ADN_LCBR_V1.zip
bash B286_ADN_LCBR_V1/start_on_autodl.sh
tail -F /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/codex_b286_lcbr.log
```

启动脚本自动使用现有 mpdnet-r10，无须 `conda activate`。通过 nohup 后台运行，SSH 或热点断线不会终止该任务。
与 B284/B285 共用 `codex_b271_night.lock`；若它们仍在运行，本实验等待 GPU 锁，不抢占。
训练和评分均支持重跑同一命令恢复：训练从已提交 epoch 恢复，评分从已提交 chunk/SCR 恢复。
不要修改已有输出内的代码与清单，不要删除运行中的数据缓存。

默认输出：`output_b286_adn_lcbr_v1/`。
中规模完成后请提供：`pd_scr_medium/b286_metrics.csv`、`b286_comparisons.csv`、`b286_curves.csv` 和 `figures/b286_pd_scr_pfa_1e-04.pdf`。

已有选中权重需要大规模评估时：

```bash
bash B286_ADN_LCBR_V1/start_on_autodl.sh --stage score --eval-size full
```

这是扩大**评估**样本量，模型仍是上述16k/6epoch匹配续训权重，不冒充30k从头训练。
仅在原始分数可用、权重/场景/运行时匹配且数值回放通过时复用 B284 ADN 和本包中规模分数前缀；其他部分独立推理。

## 必需的既有文件

- `SIM_R10_IQ512_TRAIN30000_VAL5000_SEED20261009_V1/` 的 HDF5、contract、audit。
- `output_b280_full_ablation_v1/A0/{best.pt,training_contract.json}`。
- `output_b284_tfse_cgcr_factorial_v1/ADN/{best.pt,training_contract.json}`，及 `pd_scr_full/{protocol_frozen.json,progress.json}`。
- `output_sim_r10_b270_wvd_rebuilt_v1/` 的完整 WVD TRAIN/VAL 缓存及其 contract，或通过 `--cache-dir` 指定已验证缓存。

B284 原始 score `.npy` 可选：缺少时重算对照分数，绝不凭 CSV/PDF 合成曲线。
无须旧的 B242/B247/B263/B268/B269 特征 `.npy`，这些不属于本实验依赖。
预留约1GiB用于两组训练权重与状态，另留256MiB用于分数/图表；缺失 WVD 缓存需要额外重建空间，优先保留现有缓存。

## 软件验证

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/B286_ADN_LCBR_V1
python -m unittest discover -s tests -v
```

软件测试包含原 ADN 函数一致性、真实224输入前反传、模块梯度、BN冻结、训练/评分中断恢复及统计/绘图。
软件测试的合成数据不代表真实雷达 Pd。AutoDL 启动后仍先完成真实5k VAL回放和三步优化器 canary，再正式训练。

本包仅使用现有 torch/numpy/h5py/matplotlib，无须安装 BasicSR/timm 或额外 CUDA 扩展。
MIT 署名保留在 `third_party/BGAI_LICENSE.txt`；详细借鉴和修改记录见 `SOURCE_PROVENANCE.json`。
