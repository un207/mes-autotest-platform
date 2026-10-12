package com.xwj.mes.common.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

import java.util.List;

/**
 * Web 层配置：CORS 白名单与请求体大小限制。
 *
 * <p>CORS 不使用 {@code *}，只放行 M4 前端（Vite 本地端口）与脚本调试用的来源，避免形成
 * 过宽的同源放宽。生产部署时通过环境变量覆盖。</p>
 */
@ConfigurationProperties(prefix = "mes.web")
public record WebProperties(
        @DefaultValue({"http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:3000", "http://127.0.0.1:3000"}) List<String> allowedOrigins) {
}
