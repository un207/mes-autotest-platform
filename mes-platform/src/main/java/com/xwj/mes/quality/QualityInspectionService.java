package com.xwj.mes.quality;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.xwj.mes.common.api.ErrorCode;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.common.exception.BizException;
import com.xwj.mes.common.util.SerialNoGenerator;
import com.xwj.mes.common.util.TextUtils;
import com.xwj.mes.material.MaterialBatch;
import com.xwj.mes.material.TraceNodeType;
import com.xwj.mes.material.TraceRecordService;
import com.xwj.mes.material.mapper.MaterialBatchMapper;
import com.xwj.mes.quality.dto.QualityInspectionCreateRequest;
import com.xwj.mes.quality.dto.QualityInspectionQuery;
import com.xwj.mes.quality.mapper.QualityInspectionMapper;
import com.xwj.mes.workorder.WorkOrder;
import com.xwj.mes.workorder.mapper.WorkOrderMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 质检领域服务。
 *
 * <p>核心约束：结论由数量推导，不允许人工背离；不良必须给代码，否则追溯链在不良环节断掉。</p>
 */
@Service
public class QualityInspectionService {

    private static final Logger log = LoggerFactory.getLogger(QualityInspectionService.class);
    private static final String PREFIX_INSPECT = "QI";

    private final QualityInspectionMapper inspectionMapper;
    private final WorkOrderMapper workOrderMapper;
    private final MaterialBatchMapper materialBatchMapper;
    private final TraceRecordService traceRecordService;

    public QualityInspectionService(QualityInspectionMapper inspectionMapper,
                                    WorkOrderMapper workOrderMapper,
                                    MaterialBatchMapper materialBatchMapper,
                                    TraceRecordService traceRecordService) {
        this.inspectionMapper = inspectionMapper;
        this.workOrderMapper = workOrderMapper;
        this.materialBatchMapper = materialBatchMapper;
        this.traceRecordService = traceRecordService;
    }

    @Transactional(rollbackFor = Exception.class)
    public QualityInspection create(QualityInspectionCreateRequest req) {
        WorkOrder order = workOrderMapper.selectByOrderNo(req.orderNo().trim());
        if (order == null) {
            throw BizException.notFound("工单不存在: " + req.orderNo());
        }

        String batchNo = TextUtils.nullIfBlank(req.batchNo());
        if (batchNo != null) {
            MaterialBatch batch = materialBatchMapper.selectByBatchNo(batchNo);
            if (batch == null) {
                throw BizException.notFound("物料批次不存在: " + batchNo);
            }
            if (StringUtils.hasText(batch.getOrderNo()) && !batch.getOrderNo().equals(req.orderNo().trim())) {
                throw BizException.stateConflict("批次[" + batchNo + "]已绑定工单["
                        + batch.getOrderNo() + "]，与本次质检工单不一致");
            }
        }

        int inspectQty = req.inspectQty();
        Integer qualified = req.qualifiedQty();
        Integer defective = req.defectiveQty();

        if (qualified == null && defective == null) {
            qualified = inspectQty;
            defective = 0;
        } else if (qualified == null) {
            qualified = inspectQty - defective;
        } else if (defective == null) {
            defective = inspectQty - qualified;
        }
        if (qualified < 0 || defective < 0) {
            throw new BizException(ErrorCode.PARAM_INVALID, "合格数量与不良数量均不能为负数");
        }
        if (qualified + defective != inspectQty) {
            throw new BizException(ErrorCode.PARAM_INVALID,
                    "合格数量(" + qualified + ") + 不良数量(" + defective + ") 必须等于检验数量(" + inspectQty + ")");
        }

        String defectCode = TextUtils.nullIfBlank(req.defectCode());
        if (defective > 0 && defectCode == null) {
            throw new BizException(ErrorCode.PARAM_INVALID, "存在不良品时，不良代码不能为空");
        }

        InspectResult derived = InspectResult.derive(defective);
        if (req.result() != null && req.result() != derived) {
            throw new BizException(ErrorCode.PARAM_INVALID,
                    "质检结论与数量不符：不良数 " + defective + " 应判为 " + derived.getLabel());
        }

        QualityInspection inspection = new QualityInspection();
        inspection.setInspectNo(SerialNoGenerator.next(PREFIX_INSPECT));
        inspection.setOrderNo(req.orderNo().trim());
        inspection.setBatchNo(batchNo);
        inspection.setInspectType(req.inspectType());
        inspection.setInspectQty(inspectQty);
        inspection.setQualifiedQty(qualified);
        inspection.setDefectiveQty(defective);
        inspection.setDefectCode(defectCode);
        inspection.setResult(derived);
        inspection.setInspector(req.inspector().trim());
        inspection.setInspectTime(req.inspectTime() == null ? LocalDateTime.now() : req.inspectTime());
        inspection.setRemark(TextUtils.nullIfBlank(req.remark()));

        inspectionMapper.insert(inspection);

        if (batchNo != null) {
            traceRecordService.record(TraceNodeType.INSPECT, batchNo, inspection.getOrderNo(),
                    req.inspectType().getLabel() + "：" + derived.getLabel()
                            + "（合格 " + qualified + " / 不良 " + defective + "）",
                    inspection.getInspector());
        }

        log.info("质检录入成功 inspectNo={} orderNo={} type={} result={}",
                inspection.getInspectNo(), inspection.getOrderNo(), req.inspectType(), derived);
        return inspection;
    }

    public PageResult<QualityInspection> page(QualityInspectionQuery query) {
        LambdaQueryWrapper<QualityInspection> wrapper = new LambdaQueryWrapper<QualityInspection>()
                .eq(StringUtils.hasText(query.getOrderNo()), QualityInspection::getOrderNo, query.getOrderNo())
                .eq(StringUtils.hasText(query.getBatchNo()), QualityInspection::getBatchNo, query.getBatchNo())
                .eq(query.getInspectType() != null, QualityInspection::getInspectType, query.getInspectType())
                .eq(query.getResult() != null, QualityInspection::getResult, query.getResult())
                .eq(StringUtils.hasText(query.getDefectCode()), QualityInspection::getDefectCode, query.getDefectCode())
                .orderByDesc(QualityInspection::getId);

        Page<QualityInspection> page = inspectionMapper.selectPage(
                new Page<>(query.getPageNum(), query.getPageSize()), wrapper);
        return PageResult.of(page.getTotal(), page.getCurrent(), page.getSize(), page.getRecords());
    }

    public QualityInspection detail(String inspectNo) {
        QualityInspection inspection = inspectionMapper.selectOne(
                new LambdaQueryWrapper<QualityInspection>().eq(QualityInspection::getInspectNo, inspectNo));
        if (inspection == null) {
            throw BizException.notFound("质检单不存在: " + inspectNo);
        }
        return inspection;
    }

    /** 不良追溯：按工单列出全部不合格记录。 */
    public List<QualityInspection> defectsByOrder(String orderNo) {
        if (workOrderMapper.selectByOrderNo(orderNo) == null) {
            throw BizException.notFound("工单不存在: " + orderNo);
        }
        return inspectionMapper.selectDefectsByOrderNo(orderNo);
    }

    /** 不良代码分布，供质量看板与统计接口使用。 */
    public List<Map<String, Object>> defectSummary() {
        return inspectionMapper.sumDefectsByCode();
    }
}
