package com.xwj.mes.material;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.xwj.mes.common.api.ErrorCode;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.common.exception.BizException;
import com.xwj.mes.common.util.SerialNoGenerator;
import com.xwj.mes.common.util.TextUtils;
import com.xwj.mes.material.dto.MaterialBatchCreateRequest;
import com.xwj.mes.material.dto.MaterialBatchQuery;
import com.xwj.mes.material.mapper.MaterialBatchMapper;
import com.xwj.mes.workorder.WorkOrder;
import com.xwj.mes.workorder.mapper.WorkOrderMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 物料批次服务。
 */
@Service
public class MaterialBatchService {

    private static final Logger log = LoggerFactory.getLogger(MaterialBatchService.class);
    private static final String PREFIX_BATCH = "MB";

    private final MaterialBatchMapper materialBatchMapper;
    private final WorkOrderMapper workOrderMapper;
    private final TraceRecordService traceRecordService;

    public MaterialBatchService(MaterialBatchMapper materialBatchMapper,
                                WorkOrderMapper workOrderMapper,
                                TraceRecordService traceRecordService) {
        this.materialBatchMapper = materialBatchMapper;
        this.workOrderMapper = workOrderMapper;
        this.traceRecordService = traceRecordService;
    }

    @Transactional(rollbackFor = Exception.class)
    public MaterialBatch create(MaterialBatchCreateRequest req) {
        String batchNo = TextUtils.nullIfBlank(req.batchNo());
        batchNo = batchNo == null ? SerialNoGenerator.next(PREFIX_BATCH) : batchNo;

        if (materialBatchMapper.selectByBatchNo(batchNo) != null) {
            throw BizException.duplicated("批次号已存在: " + batchNo);
        }

        String orderNo = TextUtils.nullIfBlank(req.orderNo());
        if (orderNo != null) {
            WorkOrder order = workOrderMapper.selectByOrderNo(orderNo);
            if (order == null) {
                throw BizException.notFound("工单不存在: " + orderNo);
            }
        }

        MaterialBatch batch = new MaterialBatch();
        batch.setBatchNo(batchNo);
        batch.setMaterialCode(req.materialCode().trim());
        batch.setMaterialName(req.materialName().trim());
        batch.setOrderNo(orderNo);
        batch.setSupplier(TextUtils.nullIfBlank(req.supplier()));
        batch.setQty(req.qty());
        batch.setUnit(TextUtils.nullIfBlank(req.unit()));
        batch.setInboundTime(req.inboundTime() == null ? LocalDateTime.now() : req.inboundTime());
        batch.setStatus(orderNo == null ? BatchStatus.IN_STOCK : BatchStatus.IN_USE);
        batch.setRemark(TextUtils.nullIfBlank(req.remark()));

        materialBatchMapper.insert(batch);
        traceRecordService.record(TraceNodeType.INBOUND, batchNo, orderNo,
                "来料入库 " + req.qty() + (batch.getUnit() == null ? "" : batch.getUnit())
                        + (orderNo == null ? "" : "，绑定工单 " + orderNo),
                batch.getSupplier());

        log.info("物料批次创建成功 batchNo={} material={} qty={} 绑定工单={}",
                batchNo, batch.getMaterialCode(), req.qty(), orderNo);
        return batch;
    }

    /**
     * 批次绑定工单。仅在批次未绑定或重复绑定同一工单时允许，防止一个批次挂两个工单导致追溯串线。
     */
    @Transactional(rollbackFor = Exception.class)
    public MaterialBatch bind(String batchNo, String orderNo) {
        MaterialBatch batch = requireBatch(batchNo);
        if (batch.getStatus() == BatchStatus.CONSUMED) {
            throw BizException.stateConflict("批次已消耗，不允许再绑定工单");
        }
        if (StringUtils.hasText(batch.getOrderNo()) && !batch.getOrderNo().equals(orderNo)) {
            throw BizException.stateConflict("批次已绑定工单[" + batch.getOrderNo() + "]，不允许改绑");
        }
        if (workOrderMapper.selectByOrderNo(orderNo) == null) {
            throw BizException.notFound("工单不存在: " + orderNo);
        }

        batch.setOrderNo(orderNo);
        batch.setStatus(BatchStatus.IN_USE);
        materialBatchMapper.updateById(batch);
        log.info("批次绑定工单 batchNo={} orderNo={}", batchNo, orderNo);
        return batch;
    }

    /** 出货/消耗：批次置为已消耗并落 OUTBOUND 节点。 */
    @Transactional(rollbackFor = Exception.class)
    public MaterialBatch outbound(String batchNo, String operator) {
        MaterialBatch batch = requireBatch(batchNo);
        if (batch.getStatus() == BatchStatus.CONSUMED) {
            throw BizException.stateConflict("批次已消耗，不可重复出货");
        }
        if (batch.getStatus() == BatchStatus.FROZEN) {
            throw BizException.stateConflict("批次处于冻结状态，不允许出货");
        }

        batch.setStatus(BatchStatus.CONSUMED);
        materialBatchMapper.updateById(batch);
        traceRecordService.record(TraceNodeType.OUTBOUND, batchNo, batch.getOrderNo(),
                "出货消耗 " + batch.getQty() + (batch.getUnit() == null ? "" : batch.getUnit()), operator);
        log.info("批次出货 batchNo={} orderNo={}", batchNo, batch.getOrderNo());
        return batch;
    }

    public PageResult<MaterialBatch> page(MaterialBatchQuery query) {
        LambdaQueryWrapper<MaterialBatch> wrapper = new LambdaQueryWrapper<MaterialBatch>()
                .eq(StringUtils.hasText(query.getMaterialCode()), MaterialBatch::getMaterialCode, query.getMaterialCode())
                .eq(StringUtils.hasText(query.getOrderNo()), MaterialBatch::getOrderNo, query.getOrderNo())
                .eq(query.getStatus() != null, MaterialBatch::getStatus, query.getStatus());

        if (StringUtils.hasText(query.getKeyword())) {
            String kw = query.getKeyword().trim();
            wrapper.and(w -> w.like(MaterialBatch::getBatchNo, kw).or().like(MaterialBatch::getMaterialName, kw));
        }
        wrapper.orderByDesc(MaterialBatch::getId);

        Page<MaterialBatch> page = materialBatchMapper.selectPage(
                new Page<>(query.getPageNum(), query.getPageSize()), wrapper);
        return PageResult.of(page.getTotal(), page.getCurrent(), page.getSize(), page.getRecords());
    }

    public MaterialBatch detail(String batchNo) {
        return requireBatch(batchNo);
    }

    public List<MaterialBatch> byOrder(String orderNo) {
        return materialBatchMapper.selectByOrderNo(orderNo);
    }

    private MaterialBatch requireBatch(String batchNo) {
        MaterialBatch batch = materialBatchMapper.selectByBatchNo(batchNo);
        if (batch == null) {
            throw BizException.notFound("物料批次不存在: " + batchNo);
        }
        return batch;
    }
}
