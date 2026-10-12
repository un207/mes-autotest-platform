package com.xwj.mes.material.mapper;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.xwj.mes.material.MaterialBatch;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

import java.util.List;

@Mapper
public interface MaterialBatchMapper extends BaseMapper<MaterialBatch> {

    @Select("SELECT * FROM mes_material_batch WHERE batch_no = #{batchNo} AND deleted = 0")
    MaterialBatch selectByBatchNo(@Param("batchNo") String batchNo);

    @Select("SELECT * FROM mes_material_batch WHERE order_no = #{orderNo} AND deleted = 0 ORDER BY id ASC")
    List<MaterialBatch> selectByOrderNo(@Param("orderNo") String orderNo);
}
