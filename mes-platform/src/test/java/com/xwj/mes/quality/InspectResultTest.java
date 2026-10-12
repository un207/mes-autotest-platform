package com.xwj.mes.quality;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 质检结论推导规则（纯函数，无外部依赖）。
 */
class InspectResultTest {

    @Test
    @DisplayName("无不良判合格")
    void shouldPassWhenNoDefect() {
        assertEquals(InspectResult.PASS, InspectResult.derive(0));
    }

    @Test
    @DisplayName("有不良即判不合格")
    void shouldFailWhenDefectExists() {
        assertEquals(InspectResult.FAIL, InspectResult.derive(1));
        assertEquals(InspectResult.FAIL, InspectResult.derive(99));
    }
}
