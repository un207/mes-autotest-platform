package com.xwj.mes.material;

import com.xwj.mes.common.exception.BizException;
import com.xwj.mes.common.util.SerialNoGenerator;
import com.xwj.mes.common.util.TextUtils;
import com.xwj.mes.material.dto.BatchTraceVO;
import com.xwj.mes.material.dto.OrderTraceVO;
import com.xwj.mes.material.dto.TraceNodeVO;
import com.xwj.mes.material.mapper.MaterialBatchMapper;
import com.xwj.mes.material.mapper.TraceRecordMapper;
import com.xwj.mes.quality.mapper.QualityInspectionMapper;
import com.xwj.mes.workorder.WorkOrder;
import com.xwj.mes.workorder.dto.WorkOrderVO;
import com.xwj.mes.workorder.mapper.WorkOrderMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 追溯服务：写追溯流水 + 正/反向追溯查询。
 *
 * <p>追溯流水只增不改。任何改变批次或工单状态的业务动作都应在此留痕，
 * 否则「结果可追溯」就只是句空话 —— 这也是 M2 阶段 SQL 落库校验的重点表。</p>
 */
@Service
public class TraceRecordService {

    private static final Logger log = LoggerFactory.getLogger(TraceRecordService.class);
    private static final String PREFIX_TRACE = "TR";

    private final TraceRecordMapper traceRecordMapper;
    private final MaterialBatchMapper materialBatchMapper;
    private final WorkOrderMapper workOrderMapper;
    private final QualityInspectionMapper qualityInspectionMapper;

    public TraceRecordService(TraceRecordMapper traceRecordMapper,
                              MaterialBatchMapper materialBatchMapper,
                              WorkOrderMapper workOrderMapper,
                              QualityInspectionMapper qualityInspectionMapper) {
        this.traceRecordMapper = traceRecordMapper;
        this.materialBatchMapper = materialBatchMapper;
        this.workOrderMapper = workOrderMapper;
        this.qualityInspectionMapper = qualityInspectionMapper;
    }

    @Transactional(rollbackFor = Exception.class)
    public TraceRecord record(TraceNodeType nodeType, String batchNo, String orderNo,
                              String nodeDesc, String operator) {
        TraceRecord record = new TraceRecord();
        record.setTraceNo(SerialNoGenerator.next(PREFIX_TRACE));
        record.setBatchNo(batchNo);
        record.setOrderNo(orderNo);
        record.setNodeType(nodeType);
        record.setNodeDesc(TextUtils.normalize(nodeDesc));
        record.setOperator(TextUtils.nullIfBlank(operator));
        record.setTraceTime(LocalDateTime.now());
        traceRecordMapper.insert(record);
        return record;
    }

    /**
     * 报工落投产追溯节点。工单上绑定的每个批次各留一条，未绑定批次则无追溯对象，静默跳过。
     */
    @Transactional(rollbackFor = Exception.class)
    public void recordProduce(String orderNo, int qty, String operator) {
        List<MaterialBatch> batches = materialBatchMapper.selectByOrderNo(orderNo);
        if (batches.isEmpty()) {
            log.debug("工单 {} 未绑定物料批次，跳过投产追溯落点", orderNo);
            return;
        }
        for (MaterialBatch batch : batches) {
            record(TraceNodeType.PRODUCE, batch.getBatchNo(), orderNo,
                    "投产报工 " + qty + " 件", operator);
        }
    }

    /** 正向追溯：批次 → 流向的工单 + 全链路节点。 */
    public BatchTraceVO traceBatch(String batchNo) {
        MaterialBatch batch = materialBatchMapper.selectByBatchNo(batchNo);
        if (batch == null) {
            throw BizException.notFound("物料批次不存在: " + batchNo);
        }
        List<TraceNodeVO> nodes = traceRecordMapper.selectByBatchNo(batchNo).stream()
                .map(TraceNodeVO::from)
                .toList();
        return new BatchTraceVO(batch, batch.getOrderNo(), nodes);
    }

    /** 反向追溯：工单 → 用到的全部批次 + 节点流水 + 不良明细。 */
    public OrderTraceVO traceOrder(String orderNo) {
        WorkOrder order = workOrderMapper.selectByOrderNo(orderNo);
        if (order == null) {
            throw BizException.notFound("工单不存在: " + orderNo);
        }
        List<MaterialBatch> batches = materialBatchMapper.selectByOrderNo(orderNo);
        List<TraceNodeVO> nodes = traceRecordMapper.selectByOrderNo(orderNo).stream()
                .map(TraceNodeVO::from)
                .toList();
        return new OrderTraceVO(WorkOrderVO.from(order), batches, nodes,
                qualityInspectionMapper.selectDefectsByOrderNo(orderNo));
    }
}
