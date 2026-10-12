package com.xwj.mes.common.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.CorsRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * 全局 CORS 配置，来源白名单见 {@link WebProperties}。
 */
@Configuration
public class WebMvcConfig implements WebMvcConfigurer {

    private final WebProperties webProperties;

    public WebMvcConfig(WebProperties webProperties) {
        this.webProperties = webProperties;
    }

    @Override
    public void addCorsMappings(CorsRegistry registry) {
        registry.addMapping("/api/**")
                .allowedOrigins(webProperties.allowedOrigins().toArray(new String[0]))
                .allowedMethods("GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS")
                .allowedHeaders("*")
                .exposedHeaders(RequestIdFilter.HEADER_TRACE_ID)
                .allowCredentials(true)
                .maxAge(3600);
    }
}
