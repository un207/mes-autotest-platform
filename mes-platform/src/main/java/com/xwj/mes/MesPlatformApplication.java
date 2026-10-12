package com.xwj.mes;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * 迷你 MES 后端启动类（自动化测试平台的被测对象）。
 */
@SpringBootApplication
@EnableTransactionManagement
@ConfigurationPropertiesScan
public class MesPlatformApplication {

    public static void main(String[] args) {
        SpringApplication.run(MesPlatformApplication.class, args);
    }
}
