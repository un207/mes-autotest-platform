package com.xwj.mes.common.util;

import org.springframework.util.StringUtils;

/**
 * 文本清洗工具。设备上报的「脏数据」在入库前统一过这一层。
 */
public final class TextUtils {

    private TextUtils() {
    }

    /** 去首尾空白并折叠内部连续空白；null 返回 null。 */
    public static String normalize(String text) {
        if (text == null) {
            return null;
        }
        return text.trim().replaceAll("\\s+", " ");
    }

    /** 去空白后为空则返回 null，便于统一走「空值不写入」的入库策略。 */
    public static String nullIfBlank(String text) {
        return StringUtils.hasText(text) ? text.trim() : null;
    }
}
