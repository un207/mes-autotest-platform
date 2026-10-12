package com.xwj.mes.workorder;

import com.xwj.mes.common.api.ErrorCode;
import com.xwj.mes.common.exception.BizException;
import com.xwj.mes.material.TraceRecordService;
import com.xwj.mes.workorder.dto.WorkOrderCreateRequest;
import com.xwj.mes.workorder.dto.WorkOrderVO;
import com.xwj.mes.workorder.dto.WorkReportCreateRequest;
import com.xwj.mes.workorder.mapper.WorkOrderMapper;
import com.xwj.mes.workorder.mapper.WorkReportMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.LocalDateTime;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * 工单状态机与数量守恒的单元测试（不依赖数据库，{@code mvn test} 可离线通过）。
 *
 * <p>这些规则是 M2 阶段接口用例的设计蓝本：单元测试守住规则，接口用例守住契约。</p>
 */
class WorkOrderServiceTest {

    private static final String ORDER_NO = "WO-TEST-0001";

    private WorkOrderMapper workOrderMapper;
    private WorkReportMapper workReportMapper;
    private TraceRecordService traceRecordService;
    private WorkOrderService service;

    @BeforeEach
    void setUp() {
        workOrderMapper = mock(WorkOrderMapper.class);
        workReportMapper = mock(WorkReportMapper.class);
        traceRecordService = mock(TraceRecordService.class);
        service = new WorkOrderService(workOrderMapper, workReportMapper, traceRecordService);
    }

    private WorkOrder order(OrderStatus status, int planQty, int finished, int qualified, int defective) {
        WorkOrder order = new WorkOrder();
        order.setId(1L);
        order.setOrderNo(ORDER_NO);
        order.setProductCode("P-1001");
        order.setProductName("法兰盘 A 型");
        order.setPlanQty(planQty);
        order.setFinishedQty(finished);
        order.setQualifiedQty(qualified);
        order.setDefectiveQty(defective);
        order.setStatus(status);
        return order;
    }

    private WorkReportCreateRequest report(int qty, Integer qualified, Integer defective) {
        return new WorkReportCreateRequest(qty, qualified, defective, "徐伟杰", "EQ-001", null, null);
    }

    @Test
    @DisplayName("报工成功：累计数量正确，首报自动流转为生产中")
    void reportShouldAccumulateAndSwitchStatus() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(order(OrderStatus.DISPATCHED, 500, 0, 0, 0));

        WorkOrderVO vo = service.report(ORDER_NO, report(100, 96, 4));

        assertEquals(OrderStatus.IN_PROGRESS, vo.getStatus());
        assertEquals(100, vo.getFinishedQty());
        assertEquals(96, vo.getQualifiedQty());
        assertEquals(4, vo.getDefectiveQty());

        ArgumentCaptor<WorkOrder> captor = ArgumentCaptor.forClass(WorkOrder.class);
        verify(workOrderMapper, times(1)).updateById(captor.capture());
        assertEquals(OrderStatus.IN_PROGRESS, captor.getValue().getStatus());
        verify(traceRecordService, times(1)).recordProduce(ORDER_NO, 100, "徐伟杰");
    }

    @Test
    @DisplayName("报工失败：合格数 + 不良数 不等于报工数时应拒绝")
    void reportShouldRejectQtyMismatch() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(order(OrderStatus.DISPATCHED, 500, 0, 0, 0));

        BizException ex = assertThrows(BizException.class, () -> service.report(ORDER_NO, report(100, 60, 30)));
        assertEquals(ErrorCode.PARAM_INVALID.getCode(), ex.getCode());
        verify(workReportMapper, never()).insert(any(WorkReport.class));
    }

    @Test
    @DisplayName("报工失败：累计数量超过计划数量应拦截")
    void reportShouldRejectOverProduction() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(order(OrderStatus.IN_PROGRESS, 100, 90, 88, 2));

        BizException ex = assertThrows(BizException.class, () -> service.report(ORDER_NO, report(20, 20, 0)));
        assertEquals(ErrorCode.STATE_CONFLICT.getCode(), ex.getCode());
        verify(workReportMapper, never()).insert(any(WorkReport.class));
    }

    @Test
    @DisplayName("报工失败：未派工（新建）状态不允许报工")
    void reportShouldRejectWhenNotDispatched() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(order(OrderStatus.NEW, 500, 0, 0, 0));

        BizException ex = assertThrows(BizException.class, () -> service.report(ORDER_NO, report(10, 10, 0)));
        assertEquals(ErrorCode.STATE_CONFLICT.getCode(), ex.getCode());
    }

    @Test
    @DisplayName("报工失败：工单不存在返回 40400")
    void reportShouldFailWhenOrderMissing() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(null);

        BizException ex = assertThrows(BizException.class, () -> service.report(ORDER_NO, report(10, 10, 0)));
        assertEquals(ErrorCode.NOT_FOUND.getCode(), ex.getCode());
    }

    @Test
    @DisplayName("报工入参：只传不良数时合格数自动推算")
    void reportShouldDeriveQualifiedQty() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(order(OrderStatus.IN_PROGRESS, 500, 0, 0, 0));

        WorkOrderVO vo = service.report(ORDER_NO, report(50, null, 5));

        assertEquals(45, vo.getQualifiedQty());
        assertEquals(5, vo.getDefectiveQty());
    }

    @Test
    @DisplayName("创建工单：计划结束时间早于开始时间应拒绝")
    void createShouldRejectInvertedPlanTime() {
        WorkOrderCreateRequest req = new WorkOrderCreateRequest("P-1001", "法兰盘 A 型", 100, null, null,
                LocalDateTime.of(2026, 10, 11, 10, 0), LocalDateTime.of(2026, 10, 11, 8, 0), null);

        BizException ex = assertThrows(BizException.class, () -> service.create(req));
        assertEquals(ErrorCode.PARAM_INVALID.getCode(), ex.getCode());
        verify(workOrderMapper, never()).insert(any(WorkOrder.class));
    }

    @Test
    @DisplayName("创建工单：初始状态为新建，计数量归零")
    void createShouldInitState() {
        WorkOrderCreateRequest req = new WorkOrderCreateRequest("P-1001", "法兰盘 A 型", 100, "L01", "一号车间",
                null, null, "备注");

        WorkOrderVO vo = service.create(req);

        assertEquals(OrderStatus.NEW, vo.getStatus());
        assertEquals(0, vo.getFinishedQty());
        assertEquals(0, vo.getQualifiedQty());
        assertEquals(0, vo.getDefectiveQty());
        assertEquals("L01", vo.getLineCode());
        verify(workOrderMapper, times(1)).insert(any(WorkOrder.class));
    }

    @Test
    @DisplayName("关闭工单：新建状态不允许关闭")
    void closeShouldRejectNewOrder() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(order(OrderStatus.NEW, 100, 0, 0, 0));

        BizException ex = assertThrows(BizException.class, () -> service.close(ORDER_NO, null));
        assertEquals(ErrorCode.STATE_CONFLICT.getCode(), ex.getCode());
    }

    @Test
    @DisplayName("关闭工单：重复关闭应拒绝")
    void closeShouldRejectDuplicatedClose() {
        when(workOrderMapper.selectByOrderNoForUpdate(ORDER_NO)).thenReturn(order(OrderStatus.CLOSED, 100, 100, 98, 2));

        BizException ex = assertThrows(BizException.class, () -> service.close(ORDER_NO, null));
        assertEquals(ErrorCode.STATE_CONFLICT.getCode(), ex.getCode());
    }
}
