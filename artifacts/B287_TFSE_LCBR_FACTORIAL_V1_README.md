# B287：TFSE × LCBR 完整四组，两个条件都要验证

本包补齐上一轮B286尚未包含的 **ADN + TFSE + LCBR**，主图严格四条线：

| 组别 | TFSE | LCBR | 来源 |
|---|---:|---:|---|
| ADN | 0 | 0 | 复用B284的匹配续训对照 |
| ADN + TFSE | 1 | 0 | 复用B282 control，即B284图中的TFSE组 |
| ADN + LCBR | 0 | 1 | 优先复用已完成B286的LCBR组 |
| ADN + TFSE + LCBR (Ours) | 1 | 1 | 本包新增组合组 |

必须分别查看：

1. **ADN + LCBR 对比 ADN**：模块独立作用。
2. **ADN + TFSE + LCBR 对比 ADN + TFSE**：模块在前端已有改进时的额外作用。

只有前一项有效不够。报告中两个对照各自列出D80、D90、Pd@0和独立H0实际虚警。
`two_required_checks`将两项D90左移分别判断；某一项D90持平、右移或无法确认，不判定为两项均改善。
未达到0.9时保留NA；不填造一个D90。该判断只是DEV描述性筛选，不能替代实际虚警与不确定性分析或独立测试。

LCBR仍是B286的同一个模块、同一接入位置和相同初始化种子；没有因TFSE组而换成另一个模块。
借鉴来源为 **Broadcast-Gated Attention With Identity Adaptive Integration for Efficient Image Super-Resolution**，IEEE TIP2026，DOI<https://doi.org/10.1109/TIP.2026.3657640>，MIT作者代码<https://github.com/bbbolt/BGAI>。
详细修改和MIT说明完整保留在`b286_reference/SOURCE_PROVENANCE.json`与`b286_reference/third_party/BGAI_LICENSE.txt`。
当前仍是候选适配，真实Pd提升和创新有效性尚未通过AutoDL结果确认。

## 训练公平性

- ADN与ADN+LCBR都从原B280 A0的同一权重起点进行匹配续训。
- TFSE与TFSE+LCBR都从原B280 A1的同一权重起点进行匹配续训。
- **组合组从原A1开始，不是在已续训的TFSE control上再额外多训练一轮。**
- 全部匹配已有B282/B284预算：16k TRAIN、5k VAL、6epoch、batch32，骨干LR1e-5、新模块LR3e-4、Adam、weight_decay1e-4、CE only。
- TFSE前端冻结；原BN仿射参数和运行统计冻结；其余CNN/FC和新模块训练。
- 两个因子层级均保留原ADN的8个SimAM；LCBR接在完整layer2之后、layer3之前。
- 选模沿用对应原A0/A1的VAL pAUC@0.01代理和CE+0.01约束；校准、AUDIT、H1分数不参与训练和选模。
- 全部不使用CGCR、TFCG、Tail或phase-ARS。

## 已有任务怎么处理

如果B286已经运行，让它完成，B287通过同一个GPU锁等待，随后核对并复用B286的LCBR权重/可用原始分数。
如果B286还没启动，可直接只启动本包：它会在自己的独立输出下补训缺失的ADN+LCBR，只训练这一个独立候选，不训练BGMSA参考组。
若旧B286只有部分结果，本包保留它们，在自己的目录补齐该单元；不改写旧B286目录。
已完成的ADN、TFSE及可复用LCBR均不重训。每次运行会记录固定的standalone来源，恢复时不偷偷切换权重。

## 上传与启动

将ZIP上传到`/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1`，然后：

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1 &&
unzip -n B287_TFSE_LCBR_FACTORIAL_V1.zip &&
bash B287_TFSE_LCBR_FACTORIAL_V1/start_on_autodl.sh
```

```bash
tail -F /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/codex_b287_tfse_lcbr.log
```

启动器自动使用现有mpdnet-r10，nohup后台运行；热点/SSH断开不会终止任务。正在执行的B285/B286先持有锁时，本实验等待。
训练从已提交epoch恢复，评分从已提交chunk/SCR恢复；重新执行相同启动命令即可，不要修改已运行目录的代码。

默认仅中规模评估：CAL300k、AUDIT200k、每个SCR512个H1，37点-24…+12dB，Pfa=1e-4。
Ours用黑色实线倒三角；坐标SCR(dB)、Pd，上方标明名义Pfa。
不同模型各自用独立CAL确定阈值，再在同一AUDIT/H1场景上计算真实结果。

输出：`output_b287_tfse_lcbr_factorial_v1/pd_scr_medium/`，请提供：

- `b287_metrics.csv`、`b287_comparisons.csv`、`b287_report.json`；
- `figures/b287_pd_scr_pfa_1e-04.pdf`；
- `b287_ablation_table_pfa_1e-04.pdf`。

中规模通过后，扩大评估而保持选中权重不变：

```bash
bash B287_TFSE_LCBR_FACTORIAL_V1/start_on_autodl.sh --stage score --eval-size full
```

完整评估为CAL3M、AUDIT1M、H1=1024×37，两种Pfa为1e-4、1e-5；不是自动重新做30k从头训练。
完整原始分数仅在权重、场景、运行时一致且数值探针回放通过时复用；找不到原始分数则实际重新推理，不使用CSV/PDF拼接曲线。

## 依赖与磁盘

依赖原IQ bank、B280 A0/A1 best.pt与contract、B282 control best.pt与contract、B284 ADN best.pt与contract及其完整评估协议/进度。
`output_b286_adn_lcbr_v1/LCBR`与对应原始分数可选，完成后优先复用。
只有缺失的WVD+LCBR需要完整TRAIN/VAL WVD缓存，优先保留`output_sim_r10_b270_wvd_rebuilt_v1/`。
补训组合组约需预留1GiB，两个候选均缺失时约需2GiB，另留256MiB用于分数/图表。
不需要旧B242/B247/B263/B268/B269特征数组。无新依赖或CUDA扩展。

软件检查：

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1/B287_TFSE_LCBR_FACTORIAL_V1
python -m unittest discover -s tests -v
```

测试用合成数据只验证软件；实际服务器启动还要完成原A1和TFSE control的5k VAL回放与三步优化器canary。
