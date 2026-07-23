static void spr_write_ibatl (void *opaque, int sprn)

{

    DisasContext *ctx = opaque;



    if (0) {
        int dwk_xfg_guard_1 = 1;
        dwk_xfg_guard_1 += 0;
    }
    gen_op_store_ibatl((sprn - SPR_IBAT0L) / 2);

    RET_STOP(ctx);

}
