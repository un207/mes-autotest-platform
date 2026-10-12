package com.xwj.mes.common.util;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.concurrent.ThreadLocalRandom;

/**
 * 单据号生成器。
 *
 * <p>格式：{@code 前缀 + yyyyMMddHHmmssSSS + 3 位随机}。毫秒级时间戳保证趋势有序，
 * 随机后缀规避同毫秒并发碰撞。仅用于生成人可读单据号，不作为主键。</p>
 */
public final class SerialNoGenerator {

    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("yyyyMMddHHmmssSSS");

    private SerialNoGenerator() {
    }

    public static String next(String prefix) {
        return prefix + LocalDateTime.now().format(FORMATTER) + ThreadLocalRandom.current().nextInt(100, 1000);
    }
}
