# 桌面待办 DesktopTodo

一个为 **Ubuntu 22.04 + GNOME Wayland** 编写的原生桌面待办应用。使用 Python 与 GTK4，不依赖 Electron；界面采用半透明圆角面板，并自动跟随系统深浅色。

## 功能

- 按截止时间排序：逾期、今天、未来的待办分组展示，支持日 / 周 / 月视图。
- 点击待办查看详细说明、完整截止时间与分钟级倒计时。
- 编辑标题、备注和截止日期；支持日历、时间输入及快捷日期。
- 右键待办可标记完成、编辑或删除；已完成事项单独分组，删除后 6 秒内可撤销。
- 设置中可切换中文 / English、调整窗口大小、配置开机自启。
- 原生 GTK4 窗口，无后台线程或轮询循环；窗口隐藏时停止倒计时刷新。

## 环境要求

- Ubuntu 22.04 / GNOME 42（主要测试环境）
- Python 3.10+
- PyGObject、GTK 4

Ubuntu 上安装依赖：

```bash
sudo apt install python3-gi gir1.2-gtk-4.0
```

## 运行

```bash
git clone https://github.com/<你的 GitHub 用户名>/desktoptodo.git
cd desktoptodo
./run.sh
```

也可以直接执行 `python3 main.py`。

演示模式使用临时数据，不读取或修改真实待办：

```bash
python3 main.py --demo
```

## 安装

### 使用 deb 包

从 Releases 下载对应版本的 `.deb` 后执行：

```bash
sudo apt install ./desktoptodo_1.3.1_all.deb
desktoptodo
```

也可以从源码构建：

```bash
./build-deb.sh 1.3.1
sudo apt install ./dist/desktoptodo_1.3.1_all.deb
```

### 用户级源码安装

```bash
./install.sh
./install.sh --autostart   # 可选：同时加入开机自启
```

安装后可在应用列表搜索“桌面待办”。

## 测试

```bash
python3 test_ui.py
```

当前包含 **45 项自动化交互断言**。测试使用独立应用 ID 和临时数据文件，不修改用户的真实待办数据。

## 数据与设置

- 待办：`~/.local/share/desktoptodo/todos.json`
- 设置：`~/.config/desktoptodo/settings.json`
- 可选自启入口：`~/.config/autostart/desktoptodo.desktop`

待办数据采用临时文件、`fsync` 和原子替换保存；损坏文件会备份为 `.corrupt`，避免直接覆盖原始数据。

## Wayland 说明

本应用是普通 GTK4 窗口，不使用 `wlr-layer-shell`。窗口可拖动，位置由桌面环境管理。GNOME Wayland 不允许普通应用自行嵌入壁纸或控制全局窗口层级；本版本不包含置顶、置底或贴桌面功能。

半透明为真实 ARGB 窗口效果，不包含依赖合成器的背景实时模糊。

## 项目结构

```text
.
├── main.py                 # 应用入口、窗口图标、演示模式
├── window.py               # 主窗口、设置、语言与深色模式
├── list_view.py            # 待办列表、右键菜单、撤销提示
├── detail_view.py          # 详情、编辑与日期选择
├── store.py                # 数据模型、校验与原子持久化
├── settings.py             # 设置持久化与开机自启
├── i18n.py                 # 中英文文案
├── util.py                 # 日期与倒计时格式化
├── style.css               # GTK4 主题
├── desktoptodo.svg         # 应用图标
├── desktoptodo.desktop     # 用户级桌面入口模板
├── run.sh                  # 源码启动脚本
├── install.sh              # 用户级安装脚本
├── build-deb.sh            # deb 构建脚本
└── test_ui.py              # 自动化交互测试
```

## 发布

```bash
./build-deb.sh 1.3.1
git tag -a v1.3.1 -m "DesktopTodo v1.3.1"
git push origin main --tags
```

随后可在 GitHub 创建 Release，并上传：

```text
dist/desktoptodo_1.3.1_all.deb
```

## License

MIT，详见 [LICENSE](LICENSE)。
