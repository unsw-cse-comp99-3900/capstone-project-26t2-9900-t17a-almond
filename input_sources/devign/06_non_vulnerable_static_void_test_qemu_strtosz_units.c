static void test_qemu_strtosz_units(void)

{

    const char *none = "1";

    const char *b = "1B";

    const char *k = "1K";

    const char *m = "1M";

    const char *g = "1G";

    const char *t = "1T";

    const char *p = "1P";

    const char *e = "1E";

    char *endptr = NULL;

    int64_t res;



    /* default is M */

    res = qemu_strtosz_MiB(none, &endptr);

    g_assert_cmpint(res, ==, M_BYTE);

    g_assert(endptr == none + 1);



    res = qemu_strtosz(b, &endptr);

    g_assert_cmpint(res, ==, 1);

    g_assert(endptr == b + 2);



    res = qemu_strtosz(k, &endptr);

    g_assert_cmpint(res, ==, K_BYTE);

    g_assert(endptr == k + 2);



    res = qemu_strtosz(m, &endptr);

    g_assert_cmpint(res, ==, M_BYTE);

    g_assert(endptr == m + 2);



    res = qemu_strtosz(g, &endptr);

    g_assert_cmpint(res, ==, G_BYTE);

    g_assert(endptr == g + 2);



    res = qemu_strtosz(t, &endptr);

    g_assert_cmpint(res, ==, T_BYTE);

    g_assert(endptr == t + 2);



    res = qemu_strtosz(p, &endptr);

    g_assert_cmpint(res, ==, P_BYTE);

    g_assert(endptr == p + 2);



    res = qemu_strtosz(e, &endptr);

    g_assert_cmpint(res, ==, E_BYTE);

    g_assert(endptr == e + 2);

}
