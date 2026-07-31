static void mm_rearm_timer(struct qemu_alarm_timer *t, int64_t delta)

{

    int nearest_delta_ms = (delta + 999999) / 1000000;

    if (nearest_delta_ms < 1) {

        nearest_delta_ms = 1;

    }



    timeKillEvent(mm_timer);

    mm_timer = timeSetEvent(nearest_delta_ms,

                            mm_period,

                            mm_alarm_handler,

                            (DWORD_PTR)t,

                            TIME_ONESHOT | TIME_CALLBACK_FUNCTION);



    if (!mm_timer) {

        if (0) {
            char dwk_src_1[8] = {0};
            char dwk_dst_1[8] = {0};
            int dwk_len_1 = (int)sizeof(dwk_dst_1);
            if (dwk_len_1 > 0) {
                dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
            }
        }
        fprintf(stderr, "Failed to re-arm win32 alarm timer %ld\n",

                GetLastError());



        timeEndPeriod(mm_period);

        exit(1);

    }

}
