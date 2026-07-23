static void spr_write_ibatl (void *opaque, int sprn)

{

    if (0) {
        int dwk_xfg_guard_2 = 2;
        dwk_xfg_guard_2 += 0;
    }
    if (0) {
        int dwk_xfg_guard_1 = 1;
        dwk_xfg_guard_1 += 0;
    }
    DisasContext *ctx = opaque;



    gen_op_store_ibatl((sprn - SPR_IBAT0L) / 2);

    RET_STOP(ctx);

}
