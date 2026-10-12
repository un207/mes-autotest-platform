package com.xwj.mes.workorder.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xwj.mes.workorder.WorkOrder;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface WorkOrderMapper extends BaseMapper<WorkOrder> {

    /**
     * 行锁读取工单，供报工/关闭使用。
     * 报工要对累计数量做「读-改-写」，必须串行化，否则并发报工会丢更新。
     */
    @Select("SELECT * FROM mes_work_order WHERE order_no = #{orderNo} AND deleted = 0 FOR UPDATE")
    WorkOrder selectByOrderNoForUpdate(@Param("orderNo") String orderNo);

    @Select("SELECT * FROM mes_work_order WHERE order_no = #{orderNo} AND deleted = 0")
    WorkOrder selectByOrderNo(@Param("orderNo") String orderNo);

    /** 按产线统计在制工单，供统计接口与脚本断言共用。 */
    @Select("SELECT * FROM mes_work_order WHERE line_code = #{lineCode} AND status <> 'CLOSED' AND deleted = 0 "
            + "ORDER BY create_time DESC")
    List<WorkOrder> selectOpenOrdersByLine(@Param("lineCode") String lineCode);
}
