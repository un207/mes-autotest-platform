package com.xwj.mes.common.health;

import com.xwj.mes.common.api.ApiResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import javax.sql.DataSource;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 健康检查端点。CI 与 pytest 的 session 级前置检查都打这两个口。
 *
 * <ul>
 *   <li>{@code /api/health} —— 进程存活，不触达下游。</li>
 *   <li>{@code /api/ready} —— 就绪，含 MySQL 连通性，不通直接 503，避免脚本对着半死的服务跑用例。</li>
 * </ul>
 */
@RestController
@RequestMapping("/api")
public class HealthController {

    private static final Logger log = LoggerFactory.getLogger(HealthController.class);

    private final DataSource dataSource;

    public HealthController(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @GetMapping("/health")
    public ApiResponse<Map<String, Object>> health() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("service", "mes-platform");
        body.put("status", "UP");
        return ApiResponse.ok(body);
    }

    @GetMapping("/ready")
    public ResponseEntity<ApiResponse<Map<String, Object>>> ready() {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("service", "mes-platform");

        try (Connection conn = dataSource.getConnection();
             Statement st = conn.createStatement();
             ResultSet rs = st.executeQuery("SELECT 1")) {
            rs.next();
            body.put("database", "UP");
            body.put("dbProduct", conn.getMetaData().getDatabaseProductVersion());
            body.put("status", "UP");
            return ResponseEntity.ok(ApiResponse.ok(body));
        } catch (Exception e) {
            log.error("就绪检查失败: 数据库不可达", e);
            body.put("database", "DOWN");
            body.put("status", "DOWN");
            body.put("reason", e.getClass().getSimpleName());
            return ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE).body(ApiResponse.ok(body));
        }
    }
}
