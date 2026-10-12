package com.xwj.mes.stats.mapper;

import com.xwj.mes.stats.dto.OrderYieldVO;
import com.xwj.mes.stats.dto.OverviewVO;
import com.xwj.mes.stats.dto.ProductionStatVO;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 统计查询 Mapper。
 *
 * <p>所有聚合一律下沉到 SQL 的 GROUP BY / 子查询，不在应用层捞全表再算 ——
 * 既省内存，也让「统计口径」这件事在 SQL 里一眼可审。</p>
 *
 * <p><b>注意</b>：只有包在 {@code <script>} 里的注解 SQL 才会被当作 XML 解析，
 * 其中 {@code <} / {@code >} 必须写成 {@code &lt;} / {@code &gt;}；
 * 不带 {@code <script>} 的注解 SQL 走纯文本，直接用原符号即可 —— 写错会变成 SQL 语法错误。</p>
 */
@Mapper
public interface StatsMapper {

    @Select("<script>"
            + "SELECT DATE_FORMAT(create_time, '%Y-%m-%d') AS statDate, "
            + "       line_code AS lineCode, "
            + "       COUNT(*) AS orderCount, "
            + "       IFNULL(SUM(plan_qty), 0) AS planQty, "
            + "       IFNULL(SUM(finished_qty), 0) AS finishedQty, "
            + "       IFNULL(SUM(qualified_qty), 0) AS qualifiedQty, "
            + "       IFNULL(SUM(defective_qty), 0) AS defectiveQty, "
            + "       ROUND(IFNULL(SUM(qualified_qty), 0) / NULLIF(SUM(finished_qty), 0) * 100, 2) AS yieldRate "
            + "FROM mes_work_order "
            + "WHERE deleted = 0 AND create_time &gt;= #{from} AND create_time &lt; #{to} "
            + "<if test='lineCode != null and lineCode != \"\"'> AND line_code = #{lineCode} </if>"
            + "GROUP BY DATE_FORMAT(create_time, '%Y-%m-%d'), line_code "
            + "ORDER BY statDate DESC, lineCode ASC"
            + "</script>")
    List<ProductionStatVO> selectDailyProduction(@Param("from") LocalDateTime from,
                                                 @Param("to") LocalDateTime to,
                                                 @Param("lineCode") String lineCode);

    @Select("SELECT order_no AS orderNo, product_code AS productCode, plan_qty AS planQty, "
            + "       finished_qty AS finishedQty, qualified_qty AS qualifiedQty, defective_qty AS defectiveQty, "
            + "       ROUND(qualified_qty / NULLIF(finished_qty, 0) * 100, 2) AS yieldRate "
            + "FROM mes_work_order WHERE deleted = 0 AND finished_qty > 0 "
            + "ORDER BY yieldRate ASC, id DESC LIMIT #{limit}")
    List<OrderYieldVO> selectLowYieldOrders(@Param("limit") int limit);

    @Select("SELECT "
            + "(SELECT COUNT(*) FROM mes_work_order WHERE deleted = 0) AS totalOrders, "
            + "(SELECT COUNT(*) FROM mes_work_order WHERE deleted = 0 AND status <> 'CLOSED') AS openOrders, "
            + "(SELECT COUNT(*) FROM mes_work_order WHERE deleted = 0 AND status = 'CLOSED') AS closedOrders, "
            + "(SELECT IFNULL(SUM(plan_qty), 0) FROM mes_work_order WHERE deleted = 0) AS totalPlanQty, "
            + "(SELECT IFNULL(SUM(finished_qty), 0) FROM mes_work_order WHERE deleted = 0) AS totalFinishedQty, "
            + "(SELECT IFNULL(SUM(qualified_qty), 0) FROM mes_work_order WHERE deleted = 0) AS totalQualifiedQty, "
            + "(SELECT IFNULL(SUM(defective_qty), 0) FROM mes_work_order WHERE deleted = 0) AS totalDefectiveQty, "
            + "(SELECT ROUND(IFNULL(SUM(qualified_qty), 0) / NULLIF(SUM(finished_qty), 0) * 100, 2) "
            + "   FROM mes_work_order WHERE deleted = 0) AS yieldRate, "
            + "(SELECT COUNT(*) FROM mes_quality_inspection WHERE deleted = 0) AS inspectionCount, "
            + "(SELECT COUNT(*) FROM mes_quality_inspection WHERE deleted = 0 AND result = 'FAIL') AS inspectionFailCount, "
            + "(SELECT COUNT(*) FROM mes_material_batch WHERE deleted = 0) AS batchCount, "
            + "(SELECT COUNT(*) FROM mes_device_data WHERE deleted = 0) AS deviceDataCount, "
            + "(SELECT COUNT(*) FROM mes_device_data WHERE deleted = 0 AND quality_flag <> 'OK') AS deviceAbnormalCount "
            + "FROM DUAL")
    OverviewVO selectOverview();
}
