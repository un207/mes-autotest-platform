package com.xwj.mes.workorder;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.xwj.mes.common.api.ErrorCode;
import com.xwj.mes.common.api.PageResult;
import com.xwj.mes.common.exception.BizException;
import com.xwj.mes.common.util.SerialNoGenerator;
import com.xwj.mes.common.util.TextUtils;
import com.xwj.mes.material.TraceRecordService;
import com.xwj.mes.workorder.dto.CloseOrderRequest;
import com.xwj.mes.workorder.dto.DispatchRequest;
import com.xwj.mes.workorder.dto.WorkOrderCreateRequest;
import com.xwj.mes.workorder.dto.WorkOrderQuery;
import com.xwj.mes.workorder.dto.WorkOrderVO;
import com.xwj.mes.workorder.dto.WorkReportCreateRequest;
import com.xwj.mes.workorder.mapper.WorkOrderMapper;
import com.xwj.mes.workorder.mapper.WorkReportMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 工单领域服务：承载工单状态机与报工数量守恒校验。
 *
 * <p>Controller 只做参数绑定与转发，所有业务规则集中在本层，便于 M2 阶段按规则设计用例。</p>
 */
@Service
public class WorkOrderService {

    private static final Logger log = LoggerFactory.getLogger(WorkOrderService.class);

    private static final String PREFIX_ORDER = "WO";
    private static final String PREFIX_REPORT = "WR";

    private final WorkOrderMapper workOrderMapper;
    private final WorkReportMapper workReportMapper;
    private final TraceRecordService traceRecordService;

    public WorkOrderService(WorkOrderMapper workOrderMapper,
                            WorkReportMapper workReportMapper,
                            TraceRecordService traceRecordService) {
        this.workOrderMapper = workOrderMapper;
        this.workReportMapper = workReportMapper;
        this.traceRecordService = traceRecordService;
    }

    @Transactional(rollbackFor = Exception.class)
    public WorkOrderVO create(WorkOrderCreateRequest req) {
        if (req.planStartTime() != null && req.planEndTime() != null
                && req.planEndTime().isBefore(req.planStartTime())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "计划结束时间不能早于计划开始时间");
        }

        WorkOrder order = new WorkOrder();
        order.setOrderNo(SerialNoGenerator.next(PREFIX_ORDER));
        order.setProductCode(req.productCode().trim());
        order.setProductName(req.productName().trim());
        order.setPlanQty(req.planQty());
        order.setFinishedQty(0);
        order.setQualifiedQty(0);
        order.setDefectiveQty(0);
        order.setStatus(OrderStatus.NEW);
        order.setLineCode(TextUtils.nullIfBlank(req.lineCode()));
        order.setWorkshop(TextUtils.nullIfBlank(req.workshop()));
        order.setPlanStartTime(req.planStartTime());
        order.setPlanEndTime(req.planEndTime());
        order.setRemark(TextUtils.nullIfBlank(req.remark()));

        workOrderMapper.insert(order);
        log.info("工单创建成功 orderNo={} product={} planQty={}",
                order.getOrderNo(), order.getProductCode(), order.getPlanQty());
        return WorkOrderVO.from(order);
    }

    public WorkOrderVO detail(String orderNo) {
        WorkOrder order = requireOrder(orderNo);
        WorkOrderVO vo = WorkOrderVO.from(order);
        vo.setReports(workReportMapper.selectByOrderNo(orderNo));
        return vo;
    }

    public PageResult<WorkOrderVO> page(WorkOrderQuery query) {
        LambdaQueryWrapper<WorkOrder> wrapper = new LambdaQueryWrapper<WorkOrder>()
                .eq(query.getStatus() != null, WorkOrder::getStatus, query.getStatus())
                .eq(StringUtils.hasText(query.getLineCode()), WorkOrder::getLineCode, query.getLineCode())
                .eq(StringUtils.hasText(query.getProductCode()), WorkOrder::getProductCode, query.getProductCode());

        if (StringUtils.hasText(query.getKeyword())) {
            String kw = query.getKeyword().trim();
            wrapper.and(w -> w.like(WorkOrder::getOrderNo, kw).or().like(WorkOrder::getProductName, kw));
        }
        wrapper.orderByDesc(WorkOrder::getId);

        Page<WorkOrder> page = workOrderMapper.selectPage(
                new Page<>(query.getPageNum(), query.getPageSize()), wrapper);

        List<WorkOrderVO> records = page.getRecords().stream().map(WorkOrderVO::from).toList();
        return PageResult.of(page.getTotal(), page.getCurrent(), page.getSize(), records);
    }

    /** 派工：NEW / DISPATCHED 可派工，其余状态拒绝。 */
    @Transactional(rollbackFor = Exception.class)
    public WorkOrderVO dispatch(String orderNo, DispatchRequest req) {
        WorkOrder order = lockOrder(orderNo);
        if (order.getStatus() != OrderStatus.NEW && order.getStatus() != OrderStatus.DISPATCHED) {
            throw BizException.stateConflict(
                    "工单当前状态[" + order.getStatus().getLabel() + "]不允许派工");
        }
        if (req.planStartTime() != null && req.planEndTime() != null
                && req.planEndTime().isBefore(req.planStartTime())) {
            throw new BizException(ErrorCode.PARAM_INVALID, "计划结束时间不能早于计划开始时间");
        }

        order.setLineCode(req.lineCode().trim());
        if (StringUtils.hasText(req.workshop())) {
            order.setWorkshop(req.workshop().trim());
        }
        if (req.planStartTime() != null) {
            order.setPlanStartTime(req.planStartTime());
        }
        if (req.planEndTime() != null) {
            order.setPlanEndTime(req.planEndTime());
        }
        if (StringUtils.hasText(req.remark())) {
            order.setRemark(req.remark().trim());
        }
        order.setStatus(OrderStatus.DISPATCHED);

        workOrderMapper.updateById(order);
        log.info("工单派工成功 orderNo={} line={}", orderNo, order.getLineCode());
        return WorkOrderVO.from(order);
    }

    /**
     * 报工：写报工记录 + 累加计数量 + 首报自动流转 IN_PROGRESS + 落追溯节点。
     *
     * <p>数量守恒规则：合格数 + 不良数 必须等于报工数；两者都不传时按全合格处理。
     * 累计报工数不得超过计划数，超报直接拦截（这是接口用例必测的负向场景）。</p>
     */
    @Transactional(rollbackFor = Exception.class)
    public WorkOrderVO report(String orderNo, WorkReportCreateRequest req) {
        WorkOrder order = lockOrder(orderNo);
        if (!order.getStatus().reportable()) {
            throw BizException.stateConflict(
                    "工单当前状态[" + order.getStatus().getLabel() + "]不允许报工，请先派工");
        }

        int reportQty = req.reportQty();
        Integer qualified = req.qualifiedQty();
        Integer defective = req.defectiveQty();

        if (qualified == null && defective == null) {
            qualified = reportQty;
            defective = 0;
        } else if (qualified == null) {
            qualified = reportQty - defective;
        } else if (defective == null) {
            defective = reportQty - qualified;
        }

        if (qualified < 0 || defective < 0) {
            throw new BizException(ErrorCode.PARAM_INVALID, "合格数量与不良数量均不能为负数");
        }
        if (qualified + defective != reportQty) {
            throw new BizException(ErrorCode.PARAM_INVALID,
                    "合格数量(" + qualified + ") + 不良数量(" + defective + ") 必须等于报工数量(" + reportQty + ")");
        }

        int newFinished = order.getFinishedQty() + reportQty;
        if (newFinished > order.getPlanQty()) {
            throw BizException.stateConflict("累计报工数量(" + newFinished
                    + ")将超出计划数量(" + order.getPlanQty() + ")，已拦截");
        }

        LocalDateTime reportTime = req.reportTime() == null ? LocalDateTime.now() : req.reportTime();

        WorkReport report = new WorkReport();
        report.setReportNo(SerialNoGenerator.next(PREFIX_REPORT));
        report.setOrderNo(orderNo);
        report.setReportQty(reportQty);
        report.setQualifiedQty(qualified);
        report.setDefectiveQty(defective);
        report.setWorker(req.worker().trim());
        report.setEquipmentCode(TextUtils.nullIfBlank(req.equipmentCode()));
        report.setReportTime(reportTime);
        report.setRemark(TextUtils.nullIfBlank(req.remark()));
        workReportMapper.insert(report);

        order.setFinishedQty(newFinished);
        order.setQualifiedQty(order.getQualifiedQty() + qualified);
        order.setDefectiveQty(order.getDefectiveQty() + defective);
        if (order.getStatus() == OrderStatus.DISPATCHED) {
            order.setStatus(OrderStatus.IN_PROGRESS);
            order.setActualStartTime(reportTime);
        }
        workOrderMapper.updateById(order);

        traceRecordService.recordProduce(orderNo, reportQty, report.getWorker());

        log.info("报工成功 orderNo={} reportNo={} qty={} 合格={} 不良={} 累计={}/{}",
                orderNo, report.getReportNo(), reportQty, qualified, defective, newFinished, order.getPlanQty());
        return WorkOrderVO.from(order);
    }

    /** 关闭工单：DISPATCHED / IN_PROGRESS 可关闭，NEW 与已关闭拒绝。 */
    @Transactional(rollbackFor = Exception.class)
    public WorkOrderVO close(String orderNo, CloseOrderRequest req) {
        WorkOrder order = lockOrder(orderNo);
        if (order.getStatus() == OrderStatus.CLOSED) {
            throw BizException.stateConflict("工单已关闭，不可重复关闭");
        }
        if (order.getStatus() == OrderStatus.NEW) {
            throw BizException.stateConflict("工单尚未派工，不允许关闭");
        }

        order.setStatus(OrderStatus.CLOSED);
        order.setActualEndTime(LocalDateTime.now());
        if (req != null && StringUtils.hasText(req.remark())) {
            order.setRemark(req.remark().trim());
        }
        workOrderMapper.updateById(order);
        log.info("工单关闭 orderNo={} 累计报工={}", orderNo, order.getFinishedQty());
        return WorkOrderVO.from(order);
    }

    public List<WorkReport> reports(String orderNo) {
        requireOrder(orderNo);
        return workReportMapper.selectByOrderNo(orderNo);
    }

    private WorkOrder requireOrder(String orderNo) {
        WorkOrder order = workOrderMapper.selectByOrderNo(orderNo);
        if (order == null) {
            throw BizException.notFound("工单不存在: " + orderNo);
        }
        return order;
    }

    /** 事务内行锁读取，报工/派工/关闭三类写操作必须走这里。 */
    private WorkOrder lockOrder(String orderNo) {
        WorkOrder order = workOrderMapper.selectByOrderNoForUpdate(orderNo);
        if (order == null) {
            throw BizException.notFound("工单不存在: " + orderNo);
        }
        return order;
    }
}
