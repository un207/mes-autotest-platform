package com.xwj.mes.material.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xwj.mes.material.TraceRecord;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface TraceRecordMapper extends BaseMapper<TraceRecord> {

    @Select("SELECT * FROM mes_trace_record WHERE batch_no = #{batchNo} AND deleted = 0 "
            + "ORDER BY trace_time ASC, id ASC")
    List<TraceRecord> selectByBatchNo(@Param("batchNo") String batchNo);

    @Select("SELECT * FROM mes_trace_record WHERE order_no = #{orderNo} AND deleted = 0 "
            + "ORDER BY trace_time ASC, id ASC")
    List<TraceRecord> selectByOrderNo(@Param("orderNo") String orderNo);
}
