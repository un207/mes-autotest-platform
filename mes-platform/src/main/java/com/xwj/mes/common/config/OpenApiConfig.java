package com.xwj.mes.common.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Contact;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.servers.Server;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

/**
 * OpenAPI 文档配置。
 *
 * <p>M2 阶段的 pytest 用例可直接以 {@code /v3/api-docs} 为准校对路径与字段，
 * 避免脚本与后端接口契约悄悄漂移。</p>
 */
@Configuration
public class OpenApiConfig {

    @Bean
    public OpenAPI mesOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("迷你 MES 系统 API")
                        .version("1.0.0")
                        .description("工单 / 报工 / 质检 / 物料追溯 / 设备数采 接口契约（自动化测试平台的被测对象）")
                        .contact(new Contact().name("xwj")))
                .servers(List.of(new Server().url("/").description("当前服务")));
    }
}
