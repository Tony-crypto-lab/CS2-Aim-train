# CS2 Vision Lineup Assistant (Mirage V1)

一个本地运行的 CS2 副屏辅助工具（纯视觉方案）。

- ✅ 不读取游戏内存
- ✅ 不注入、不 Hook、不改游戏文件
- ✅ 仅使用屏幕截图 + OpenCV + 本地 JSON 配置

当前版本目标：
- 仅支持 `de_mirage`
- 仅支持 `T` 方
- 完成 **手动校准 + 小地图定位 + 区域识别 + 近点位匹配 + 副屏自动切图**
- 副屏默认窗口模式（可在 UI 勾选 Output Fullscreen 切换全屏）

---

## 1. 项目结构

```text
CS2-Aim-train/
├─ main.py
├─ requirements.txt
├─ README.md
├─ config/
│  ├─ app_config.json
│  ├─ zones_mirage.json
│  └─ lineups_mirage.json
├─ cs2vision/
│  ├─ __init__.py
│  ├─ models.py
│  ├─ utils.py
│  ├─ capture.py
│  ├─ roi_locator.py
│  ├─ minimap_tracker.py
│  ├─ zone_matcher.py
│  ├─ lineup_matcher.py
│  ├─ output_manager.py
│  ├─ second_screen_window.py
│  ├─ debug_overlay.py
│  └─ calibration.py
├─ assets/
│  └─ maps/
│     └─ de_mirage/
│        ├─ minimap_reference.png
│        ├─ lineups/
│        │  ├─ standby.png
│        │  ├─ t_spawn_window_smoke.png
│        │  ├─ t_spawn_connector_smoke.png
│        │  ├─ top_mid_cat_smoke.png
│        │  └─ a_ramp_jungle_smoke.png
│        ├─ view_templates/
│        │  └─ README.txt
│        └─ debug/
│           ├─ self_icon_template.png
│           └─ README.txt
└─ logs/
```

> 如果图片资源缺失，程序会自动生成占位图，确保可启动 Demo。

---

## 2. 安装步骤（Windows 10/11）

1. 安装 Python 3.11。
2. 进入项目目录：
   ```bash
   cd CS2-Aim-train
   ```
3. 创建虚拟环境并激活：
   ```bash
   py -3.11 -m venv .venv
   .venv\Scripts\activate
   ```
4. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

---

## 3. 运行步骤

```bash
python main.py
```

运行后：
- 主界面显示状态、FPS、区域、点位、置信度
- 可选择主显示器 / 副显示器
- 点击 **Start** 开始识别
- 副屏窗口默认以窗口模式显示教学图（可切换为全屏）

---

## 4. 第一次校准流程

1. 启动程序后点击 **Recalibrate**。
2. 程序会抓取当前主屏截图，并弹出 OpenCV 框选窗口。
3. 鼠标框选小地图 ROI（左上雷达区域）。
4. 输入地图名（默认 `de_mirage`）。
5. 输入阵营（默认 `T`）。
6. 保存后会写入 `config/app_config.json` 的 `minimap_roi`。

> 建议：在 CS2 里固定 HUD 缩放和分辨率，减少漂移。

---

## 5. 如何添加 Mirage 区域

编辑 `config/zones_mirage.json` 的 `zones` 列表，支持三种类型：

1. `polygon`
```json
{
  "id": "top_mid",
  "name": "Top Mid",
  "type": "polygon",
  "points": [[180,210],[270,210],[280,290],[190,300]],
  "priority": 95
}
```

2. `rect`
```json
{
  "id": "market",
  "name": "Market",
  "type": "rect",
  "rect": [35, 25, 80, 65],
  "priority": 83
}
```

3. `circle`
```json
{
  "id": "bench",
  "name": "Bench",
  "type": "circle",
  "center": [120, 60],
  "radius": 35,
  "priority": 84
}
```

注意：
- 所有坐标使用 **reference minimap 坐标系**（`minimap_reference.png`）
- `priority` 越高越优先

---

## 6. 如何添加点位图片与数据

### 第 1 步：放置图片
把教学图放到：

```text
assets/maps/de_mirage/lineups/
```

例如：
```text
assets/maps/de_mirage/lineups/my_new_smoke.png
```

### 第 2 步：编辑点位 JSON
在 `config/lineups_mirage.json` 添加一条：

```json
{
  "id": "mirage_my_new_lineup",
  "map": "de_mirage",
  "side": "T",
  "region": "Top Mid",
  "lineup_name": "My New Smoke",
  "throw_type": "Jump Throw",
  "description": "简要说明",
  "minimap_x": 230,
  "minimap_y": 250,
  "trigger_radius": 35,
  "preview_image": "assets/maps/de_mirage/lineups/my_new_smoke.png",
  "optional_view_template": "",
  "optional_heading_min": 20,
  "optional_heading_max": 90,
  "priority": 7,
  "tags": ["smoke", "mid"]
}
```

字段说明：
- 先做半径触发：`minimap_x/minimap_y + trigger_radius`
- 可选朝向约束：`optional_heading_min/max`
- 可选模板二次确认：`optional_view_template`

---

## 7. 常见问题排查

### Q1: 启动后没有检测到玩家点
- 调整小地图 ROI（重新校准）
- 检查 HUD 缩放是否变化
- 替换 `assets/maps/de_mirage/debug/self_icon_template.png` 为你的雷达箭头截图

### Q2: 副屏没有显示
- 确认 `output_monitor_index` 是否正确
- 有些系统会把副屏编号和物理顺序不一致，切换尝试 1/2/3

### Q3: 点位来回抖动
- 提高 `lineup_stable_frames`
- 增大 `lineup_hold_seconds`
- 适当降低 `trigger_radius`

### Q4: 性能太低
- 降低 `fps_limit` 到 8~10
- 提高 `detect_interval_ms`
- 减小 minimap ROI

### Q5: 没有真实资源会不会崩溃
- 不会。程序会自动创建占位图并进入 Demo 模式。

---

## 8. 后续扩展路线（建议）

1. 扩展到 5 寸串口屏：
- 新增串口输出模块，把当前匹配点位文本 + 缩略图传给 MCU
- `output_manager.py` 保持统一事件流，新增 `serial_output.py` 消费同一 payload

2. 扩展到 Dust2 / Inferno：
- 新增 `zones_dust2.json`、`lineups_dust2.json`
- 新增对应 `assets/maps/de_dust2/...`
- 在 UI 中增加 map 选择并动态切换 matcher 数据

3. 提升视角匹配精度：
- 增加多模板投票（白天/夜间、不同亮度）
- 引入特征点匹配（ORB）做次级验证
- 后续可加 homography 替换当前简化缩放映射

---

## 9. 免责声明

该工具用于本地学习与训练辅助，不应违反游戏平台协议。请自行评估风险并遵守相关条款。
