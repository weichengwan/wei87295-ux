# DoT-CVVAE 原文与旧权重诊断 V1

原文：Bai et al., *Radar target detection in sea clutter via a detection-oriented complex-valued VAE*, Signal Processing249(2026)110758, DOI:10.1016/j.sigpro.2026.110758。根据用户上传的13页PDF核对。

## 本次做什么

- 严格加载已有B225 DoT-CVVAE权重及原生IQ16网络，核验权重、源码和完整TRAIN/VAL HDF5的SHA。
- 网络只读取VAL5000做前向诊断，不训练、不修改旧权重或旧结果，不读取CAL/AUDIT/DEV-H1分数。
- 输出原生IQ16固定块、旧MAX32场景分数和诊断MEAN32的VAL分布、描述性AUC；保存时域、幅度、多普勒分数分量、重建功率和后验信息。
- MAX32保持旧算法；MEAN32仅诊断聚合影响，不自动成为新baseline，不自动选择分数最好的一组。
- 不从VAL5000估计1e-4/1e-5的Pd或阈值，样本量不足以支持可靠尾部估计。本包不会输出宣称为低虚警率正式结果的Pd图。
- native16只看IQ[256:272]，与IQ512观测长度不同，只作诊断。

## 已核实的原文对应与差异

L16确为16个连续慢时间脉冲；K4、通道32、4个编码和解码复数TCN模块、modReLU、Student-t nu5、峰值权重alpha1.7/rho1.6、KL、幅度与谱峰损失以及检测公式基本对应。

原文默认训练50轮；旧SIM模型训练25轮。原文一个IQ16快照输出一个标量；旧SIM把32个IQ16分数取MAX作为IQ512统计量。原文主要Pfa1e-3；当前全量SIM为1e-4与1e-5。目标与杂波分布也不同。旧MAX32已经有自己的场景级H0标定，不能声称其虚警概率计算有已证实错误。

论文未完整给出推理时后验均值/随机采样选择、IQ归一化与部分实现细节。图2的横向连线与正文不足以确定额外跨编码器-解码器融合公式；本包保留现有网络，不擅自加跳连并宣称作者原版。

## 所需服务器文件

```text
SIM_R10_IQ512_TRAIN30000_VAL5000_SEED20261009_V1/
  sim_r10_iq512_v1.h5
  sim_r10_iq512_v1_contract.json
output_sim_r10_b225_real_four_dl_train_v1/DoT_CVVAE/seed_20261022/
  sim_r10_final.pt
  training_contract.json
```

不要求B225原代码目录存在，原始模型源码已附入frozen_source并受SHA校验。

## AutoDL运行

将ZIP置于`/root/autodl-tmp/MTDSP_NATIVE_LMDA_V1`后：

```bash
cd /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1
unzip -n DOT_CVVAE_ORIGINAL_AUDIT_V1.zip
bash DOT_CVVAE_ORIGINAL_AUDIT_V1/start_on_autodl.sh
tail -F codex_dot_original_audit.log
```

启动器使用conda环境mpdnet-r10、nohup后台运行。SSH断开不终止后台任务；Ctrl+C退出tail只停止查看日志。独立任务锁防止重复诊断同时执行；共用`codex_b271_night.lock`等待B283等使用同一锁的GPU任务结束。等待阶段只加载CPU模型，不占GPU显存。

正式运行只推理VAL5000，即160000个原生IQ16片段，远少于全量4M场景。具体耗时看日志；完整HDF5哈希会增加一次顺序读盘。不承诺固定分钟数。

仅CPU预检：

```bash
/root/miniconda3/bin/conda run --no-capture-output -n mpdnet-r10 \
  python DOT_CVVAE_ORIGINAL_AUDIT_V1/dot_probe.py --stage preflight \
  --root /root/autodl-tmp/MTDSP_NATIVE_LMDA_V1 --device cpu
```

## 输出

每次创建新目录，不覆盖旧输出：

```text
output_dot_original_audit_v1/val_probe_时间戳/
  dot_probe_report.json
  dot_val_score_summary.csv
  dot_val_scores.csv
```

运行完成后上传前三个文件；前两个足以先看总体问题，第三个用于分布复核。

报告中的VAL AUC是描述性诊断，VAL不是独立测试，也不代表1e-4/1e-5 Pd。只看AUC不能判定极低虚警率表现。不能据此自动选最好的聚合并将其称为原文复现。

## 验证范围

`python -m unittest -v test_probe`：5个CPU测试，覆盖原文三项检测公式、与原始MAX32算法的数值一致性、归一化路径、真实格式的合成检查点/HDF5加载与哈希拒绝、报告口径和权重只读。

合成夹具测试不包含用户实际AutoDL权重或CUDA实验。实际运行结果仍待用户服务器验证。
