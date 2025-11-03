# iframe HTML 提取测试输出

这个目录用于存储从 `/api/proxy/render` 端点提取的HTML文件。

## 目录结构

```
iframe_html/
├── README.md                           # 本说明文档
├── latest.html                         # 最新渲染的HTML（软链接）
├── latest.json                         # 最新的元数据（软链接）
├── 20250103_120530_example_com.html    # 保存的HTML文件
├── 20250103_120530_example_com.json    # 对应的元数据文件
└── ...
```

## 文件命名规则

- **HTML文件**: `{timestamp}_{safe_url}.html`
  - `timestamp`: YYYYmmdd_HHMMSS 格式
  - `safe_url`: URL的安全版本（去除协议，替换特殊字符）

- **元数据文件**: `{timestamp}_{safe_url}.json`
  - 包含URL、标题、时间戳、HTML大小等信息

- **latest链接**: 始终指向最新生成的文件

## 使用说明

### 1. 提取HTML

```bash
python tests/test_iframe_html_extraction.py https://example.com
```

### 2. 查看所有保存的HTML

```bash
python tests/test_iframe_html_extraction.py --list
```

### 3. 查看特定HTML文件

```bash
python tests/test_iframe_html_extraction.py --view latest.html
```

### 4. 使用浏览器打开

```bash
# Linux/Mac
open tests/output/iframe_html/latest.html

# Windows
start tests/output/iframe_html/latest.html
```

## 元数据格式

每个HTML文件都有一个对应的JSON元数据文件：

```json
{
  "url": "https://example.com",
  "title": "Example Domain",
  "timestamp": "20250103_120530",
  "html_size": 12345,
  "filepath": "tests/output/iframe_html/20250103_120530_example_com.html"
}
```

## HTML内容特点

从 `/api/proxy/render` 提取的HTML包含以下特性：

1. **`<base>` 标签**: 自动修复资源相对路径
2. **Font Awesome CDN**: 自动注入图标库
3. **交互监听脚本**: 注入 `seenElementClickListener` 用于点击检测
4. **完整渲染**: 通过Playwright自动滚动加载所有内容

## 注意事项

- HTML文件可能很大（几MB到几十MB）
- 保存的HTML是完全自包含的，可以直接在浏览器中打开
- `latest.html` 链接会在每次新提取时自动更新
- 建议定期清理旧文件以节省磁盘空间
