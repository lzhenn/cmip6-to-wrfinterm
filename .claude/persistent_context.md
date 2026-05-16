# cmip6-to-wrfinterm — Persistent Context

## 当前任务
为 cmip6-to-wrfinterm 添加 CESM2 (CMIP6) 支持，包括数据下载、Vtable 构建、代码适配和端到端测试。

## 目标机器
- **测试机**：hqlx74（user=lzhenn，经 mini 嵌套 ssh 访问）
- **工作目录**：`/home/lzhenn/work/ust-jumper/cmip6-to-wrfinterm/`
- **访问命令**：`ssh mini 'ssh hqlx74 "..."'`
- **环境**： `source ~/.bashrc_intel20_amd`
- wrf在hqlx74运行，下载绘图在hqlx204，绘图 `conda activate postprocessing`
## CESM2 数据策略

### 数据来源
- ESGF LLNL 节点：esgf-node.llnl.gov
- 模型：CESM2，ensemble member r11i1p1f1（6hrLev/6hrPlev 最完整）

### 变量与频率规划

| CMIP6 变量 | 频率 | Table | 用途 | 状态 |
|-----------|------|-------|------|------|
| ta, ua, va, hus | 6h | 6hrLev（模式层）| 3D 大气场 | 可用 |
| ps | 6h | 6hrLev | 地面气压 | 可用 |
| zg | 6h | 6hrPlev（气压层）| 位势高度（必需）| 需确认 CESM2 是否发布 |
| tas, uas, vas | 3h | 3hr | 近地面 2m/10m | 可用 |
| huss | 3h | 3hr | 近地面比湿 | 可用 |
| psl | 6h | 6hrPlev | 海平面气压 | 可用 |
| ts / tos | daily | day | 皮温/SST | 用日均替代，无高频 |
| tsl, mrsos | monthly | Lmon | 土壤温湿度 | 月平均初始化，时间插值到目标时刻 |

### 关键设计决策
- **土壤**：月平均数据插值到模拟起始时刻，在 `parse_data` 中特殊处理
- **SST/ts**：日均 `tos`（海温）或 `ts` 插值到 6h，处理方式参考 MPI historical SST 的已有实现
- **日历**：CESM2 使用 no-leap（365天）日历，xarray 读取时需指定 `use_cftime=True`

### 最小测试数据集
下载最短时段（建议 1-2 天）的以下文件，覆盖一个完整的 ETL 测试：
- 6hrLev: ta, ua, va, hus, ps
- 6hrPlev: zg（若有）
- 3hr: tas, uas, vas, huss
- day: tos（或 ts）
- Lmon: tsl, mrsos

情景：historical，时段：尽量短（如 1990-01-01 至 1990-01-02）

## 代码改动规划（待讨论后实现）

### 1. 新建 Vtable
- `db/CESM2_6hrLev.csv`：ta, ua, va, hus, ps（3D 模式层）
- `db/CESM2_6hrPlev.csv`：zg, psl（气压层）
- `db/CESM2_3hr.csv`：tas, uas, vas, huss（近地面）
- `db/CESM2_day.csv`：tos/ts（SST，日均）
- `db/CESM2_Lmon.csv`：tsl, mrsos（土壤，月均）

### 2. 元信息表
- `db/cmip6_meta.csv`：新增 CESM2 相关行

### 3. 配置文件
- `conf/config.CESM2.ini`

### 4. 代码适配（cmip_handler.py）
- 月均土壤数据的时间插值逻辑
- 日均 SST 数据的时间插值逻辑
- no-leap 日历兼容（`use_cftime=True`）
- zg 若缺失的诊断计算（备选方案）

## 同步命令
```bash
# 本地 → mini → hqlx86
rsync -avz --exclude '.git' /Users/zhenningli/work/ust-jumper/ mini:/Users/zhenningli/work/ust-jumper/
ssh mini 'rsync -avz /Users/zhenningli/work/ust-jumper/ hqlx74:/home/lzhenn/work/ust-jumper/'
```

> 以下为自动发现，需用户合并到上面手写章节
<!-- AUTO:START — generated 2026-05-16 by /reinit-project. Do not hand-edit; rerun the command instead. -->

## 远程主机
| 主机 | user | 用途 |
|------|------|------|
| mini | zhenningli | SSH 跳板（macOS），不在其上跑计算 |
| hqlx74 | lzhenn | 主测试机；跑 `run_c2w.py`、WPS、`real.exe`、`wrf.exe` |
| hqlx204 | lzhenn | 下载 ESGF CMIP6 数据、绘图（CESM2 download.sh 在 hqlx74 受限） |

## 路径映射
| 位置 | 路径 |
|------|------|
| 本地 | `/Users/zhenningli/work/ust-jumper/cmip6-to-wrfinterm/` |
| mini | `/Users/zhenningli/work/ust-jumper/cmip6-to-wrfinterm/` |
| hqlx74 / hqlx204 | `/home/lzhenn/work/ust-jumper/cmip6-to-wrfinterm/` |
| WPS (hqlx74) | `/home/lzhenn/WRFv43-preprocess/WPS-4.3/` |
| WRF run (hqlx74) | `/home/lzhenn/WRFv43-preprocess/WRF-4.3/run/` |

## 编译 / 部署
**Build (env)**: `conda env create -f test_c2w.yml && conda activate test_c2w`
**Run (ETL)**:   `python3 run_c2w.py -m <MODEL>`   （MODEL ∈ MPI-ESM1-2-HR | BCMM | EC-Earth3 | CESM2；省略 -m 默认 MPI-ESM1-2-HR）
**Run (WPS→real→wrf)**: `bash wps_wrf_pipeline.sh`   （由 `WPS_FLAG`/`REAL_FLAG`/`WRF_FLAG` 三个开关控制；需先把 `MODEL_NAME` 改对）
**Deploy (sync)**: `rsync -avz --exclude '.git' ./ mini:.../cmip6-to-wrfinterm/ && ssh mini 'rsync -avz .../cmip6-to-wrfinterm/ hqlx74:/home/lzhenn/work/ust-jumper/cmip6-to-wrfinterm/'`

## 关键 env
- `test_c2w.yml` — conda 环境定义（xarray, netcdf4, cftime, scipy, numpy, pandas, bottleneck）；用 `conda activate test_c2w` 进入
- `~/.bashrc_intel20_amd` — hqlx74 上的 Intel20+AMD WRF 工具链（编译/运行 WPS/WRF 前 `source`）
- `conda activate postprocessing` — hqlx204 上绘图环境
- `conf/config.<MODEL>.ini` — 每个模型一份；包含数据根目录、scenario、时段、grid_flag 等
- `conf/logging_config.ini` — 日志配置；**注意**：`run_c2w.py` 用相对路径 `./conf/logging_config.ini` 引用，必须在项目根目录下启动

## 已知踩坑
- CESM2 `sample/CESM2/download.sh` 在 hqlx74 跑不通（GLIBC 太旧、Python HTTPS 失败）→ 在 hqlx204 下载或走 Globus / 镜像
- SST 输出文件名分两套：EC-Earth3 用连字符 `EC-EARTH3-SST:...`，CESM2 用下划线 `CESM2_SST:...`；WPS 软链脚本要对齐
- BCMM / EC-Earth3 默认 `config.*.ini` 内含 `/home/lzhenn/...` 绝对路径，clone 后直接跑会报路径错
- CESM2 使用 no-leap (365 天) 日历；xarray `open_*` 必须 `use_cftime=True`，否则时间轴错乱
- `run_c2w.py` 必须从项目根目录调用（`./conf/logging_config.ini` 硬编码）
- EC-Earth3 工作流需要按 vtable 表「改 config → 跑 → 再改 → 再跑」5 次，CESM2 已改为一次跑完
- 最近修复：log index typo (53a45ed)、BCMM 路径 bug (0347ec6)、MPI bug (7c44a13)

<!-- AUTO:END -->
