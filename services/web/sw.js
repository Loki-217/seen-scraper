/**
 * Service Worker - 跨域请求代理
 *
 * 功能：拦截特定域名的请求，转发到后端代理服务器，解决浏览器跨域限制
 *
 * 工作原理：
 * 1. 拦截所有网络请求（fetch 事件）
 * 2. 判断请求是否需要代理（例如 unsplash.com）
 * 3. 需要代理的请求 -> 转发到后端 /api/proxy/forward
 * 4. 不需要代理的请求 -> 直接发送
 *
 * ⚠️ 注意：需要在后端添加 /api/proxy/forward 端点
 *
 * 后端接口定义（需要添加到 services/api/app/proxy.py）：
 *
 * @router.post("/forward")
 * async def forward_request(req: ForwardRequest):
 *     """
 *     转发跨域请求
 *
 *     请求体格式：
 *     {
 *         "url": "https://unsplash.com/...",
 *         "method": "GET",
 *         "headers": {"User-Agent": "...", ...}
 *     }
 *
 *     响应体格式：
 *     {
 *         "success": true,
 *         "status": 200,
 *         "headers": {"content-type": "text/html", ...},
 *         "body": "响应内容（文本或 base64 编码的二进制数据）"
 *     }
 *     """
 *
 * 实现建议：使用 httpx 或 requests 库发送请求，处理各种 Content-Type
 */

const PROXY_API_URL = 'http://localhost:8000/api/proxy/forward';

// 🔥 需要代理的域名列表（扩展版）
// 支持精确匹配和通配符匹配
const PROXY_DOMAINS = [
    // Unsplash 相关域名（所有子域名）
    'unsplash.com',
    'images.unsplash.com',
    'api.unsplash.com',
    'source.unsplash.com',
    'cdn.unsplash.com',

    // 豆瓣相关域名（包括主站和移动站）
    'douban.com',
    'm.douban.com',           // 🔥 移动版豆瓣，AJAX API请求
    'movie.douban.com',       // 🔥 电影站
    'img1.doubanio.com',
    'img2.doubanio.com',
    'img3.doubanio.com',
    'img9.doubanio.com',
];

/**
 * 检查URL是否需要代理
 * @param {string} url - 请求的URL
 * @returns {boolean} - 是否需要代理
 */
function shouldProxy(url) {
    try {
        const urlObj = new URL(url);
        const hostname = urlObj.hostname.toLowerCase();

        // 遍历代理域名列表
        for (const domain of PROXY_DOMAINS) {
            // 精确匹配或子域名匹配
            if (hostname === domain || hostname.endsWith('.' + domain)) {
                return true;
            }
        }

        return false;
    } catch (e) {
        console.error('[SW] Invalid URL:', url, e);
        return false;
    }
}

// Service Worker 安装事件
self.addEventListener('install', (event) => {
    console.log('[SW] Service Worker 安装中...');

    // 立即激活，不等待
    self.skipWaiting();

    console.log('[SW] Service Worker 安装完成');
});

// Service Worker 激活事件
self.addEventListener('activate', (event) => {
    console.log('[SW] Service Worker 激活中...');

    // 立即控制所有页面，不等待下次加载
    event.waitUntil(
        clients.claim().then(() => {
            console.log('[SW] Service Worker 已激活并控制所有页面');
        })
    );
});

// Service Worker 拦截请求
self.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);

    // 避免拦截对代理 API 的请求（防止死循环）
    if (url.pathname.startsWith('/api/proxy/')) {
        // console.log('[SW] ⏩ 跳过代理 API 请求:', url.href);
        return; // 不拦截，直接放行
    }

    // 🔥 使用新的域名匹配函数
    const needsProxy = shouldProxy(request.url);

    if (needsProxy) {
        // 记录拦截的请求（带请求类型）
        const resourceType = getResourceType(url.pathname);
        console.log(`[SW] 🔗 拦截代理请求 [${resourceType}]:`, url.hostname, url.pathname);
        event.respondWith(handleProxyRequest(request));
    } else {
        // 不需要代理的请求，直接放行
        // 不打印日志，避免控制台刷屏
        return;
    }
});

/**
 * 根据URL路径判断资源类型
 * @param {string} pathname - URL路径
 * @returns {string} - 资源类型
 */
function getResourceType(pathname) {
    const ext = pathname.split('.').pop().toLowerCase();
    const typeMap = {
        'html': 'HTML',
        'css': 'CSS',
        'js': 'JS',
        'json': 'JSON',
        'jpg': 'Image', 'jpeg': 'Image', 'png': 'Image', 'gif': 'Image', 'webp': 'Image', 'svg': 'Image',
        'woff': 'Font', 'woff2': 'Font', 'ttf': 'Font', 'eot': 'Font',
        'mp4': 'Video', 'webm': 'Video',
        'mp3': 'Audio', 'wav': 'Audio'
    };
    return typeMap[ext] || 'Other';
}

/**
 * 处理需要代理的请求
 * @param {Request} request - 原始请求对象
 * @returns {Promise<Response>} - 代理后的响应
 */
async function handleProxyRequest(request) {
    const startTime = Date.now();
    try {
        const url = new URL(request.url);

        // 简化日志输出
        // console.log('[SW] 📤 代理请求:', request.method, url.hostname + url.pathname);

        // 转换请求头为对象格式
        const headers = {};
        for (const [key, value] of request.headers.entries()) {
            headers[key] = value;
        }

        // 构造转发请求体
        const proxyRequestBody = {
            url: request.url,
            method: request.method,
            headers: headers
        };

        // 如果原始请求有 body（POST/PUT 等），需要读取并转发
        if (request.method !== 'GET' && request.method !== 'HEAD') {
            try {
                const bodyText = await request.text();
                if (bodyText) {
                    proxyRequestBody.body = bodyText;
                }
            } catch (e) {
                console.warn('[SW] 无法读取请求 body:', e);
            }
        }

        // console.log('[SW] 📡 转发到后端:', PROXY_API_URL);

        // 发送到后端代理服务器
        const proxyResponse = await fetch(PROXY_API_URL, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(proxyRequestBody)
        });

        if (!proxyResponse.ok) {
            console.error('[SW] 后端代理返回错误:', proxyResponse.status, proxyResponse.statusText);

            // 尝试读取错误信息
            let errorDetail = '';
            try {
                const errorData = await proxyResponse.json();
                errorDetail = JSON.stringify(errorData);
            } catch (e) {
                errorDetail = await proxyResponse.text();
            }

            console.error('[SW] 错误详情:', errorDetail);

            // 降级方案：尝试直接请求（可能会失败，但至少有个回退）
            console.log('[SW] 降级：尝试直接请求原始 URL');
            return await fetch(request);
        }

        // 解析后端返回的数据
        const proxyData = await proxyResponse.json();

        // console.log('[SW] 📥 后端响应:', proxyData.success, proxyData.status);

        if (!proxyData.success) {
            console.error('[SW] 代理失败:', proxyData.error || '未知错误');

            // 降级方案：尝试直接请求
            console.log('[SW] 降级：尝试直接请求原始 URL');
            return await fetch(request);
        }

        // 根据 Content-Type 处理响应体
        let responseBody;
        const contentType = proxyData.headers?.['content-type'] || '';

        if (contentType.includes('image/') || contentType.includes('font/') || contentType.includes('octet-stream')) {
            // 二进制数据：后端应该返回 base64 编码的字符串
            if (proxyData.body_base64) {
                // 解码 base64
                const binaryString = atob(proxyData.body_base64);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }
                responseBody = bytes.buffer;
                console.log('[SW] 解码二进制数据，大小:', bytes.length, 'bytes');
            } else {
                console.warn('[SW] 缺少 body_base64 字段，使用空数据');
                responseBody = new ArrayBuffer(0);
            }
        } else {
            // 文本数据（HTML、JSON、CSS、JS 等）
            responseBody = proxyData.body || '';
            // console.log('[SW] 📄 文本数据，大小:', responseBody.length, 'chars');
        }

        // 构造响应头
        const responseHeaders = new Headers();
        if (proxyData.headers) {
            for (const [key, value] of Object.entries(proxyData.headers)) {
                // 跨域相关的头由浏览器自动处理，不需要手动设置
                if (!key.toLowerCase().startsWith('access-control-')) {
                    responseHeaders.set(key, value);
                }
            }
        }

        // 添加 CORS 头，允许跨域
        responseHeaders.set('Access-Control-Allow-Origin', '*');

        // 构造并返回响应
        const response = new Response(responseBody, {
            status: proxyData.status || 200,
            statusText: getStatusText(proxyData.status || 200),
            headers: responseHeaders
        });

        const elapsed = Date.now() - startTime;
        console.log(`[SW] ✅ 代理成功 [${elapsed}ms]:`, url.hostname, url.pathname.substring(0, 50));
        return response;

    } catch (error) {
        console.error('[SW] 代理请求发生异常:', error);
        console.error('[SW] 异常堆栈:', error.stack);

        // 降级方案：尝试直接请求（可能会因为 CORS 失败）
        try {
            console.log('[SW] 降级：尝试直接请求原始 URL');
            return await fetch(request);
        } catch (fallbackError) {
            console.error('[SW] 降级请求也失败:', fallbackError);

            // 返回错误响应
            return new Response(
                JSON.stringify({
                    error: '代理请求失败',
                    message: error.message,
                    originalUrl: request.url
                }),
                {
                    status: 502,
                    statusText: 'Bad Gateway',
                    headers: {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    }
                }
            );
        }
    }
}

/**
 * 根据状态码获取状态文本
 * @param {number} status - HTTP 状态码
 * @returns {string} - 状态文本
 */
function getStatusText(status) {
    const statusTexts = {
        200: 'OK',
        201: 'Created',
        204: 'No Content',
        301: 'Moved Permanently',
        302: 'Found',
        304: 'Not Modified',
        400: 'Bad Request',
        401: 'Unauthorized',
        403: 'Forbidden',
        404: 'Not Found',
        500: 'Internal Server Error',
        502: 'Bad Gateway',
        503: 'Service Unavailable'
    };

    return statusTexts[status] || 'Unknown';
}

console.log('[SW] Service Worker 脚本加载完成');
