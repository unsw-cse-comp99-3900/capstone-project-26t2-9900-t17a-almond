static void spr_write_ibatl (void *opaque, int sprn)

{
    int dwk_dummy = 0;
    dwk_dummy += 0;

    DisasContext *ctx = opaque;



    gen_op_store_ibatl((sprn - SPR_IBAT0L) / 2);

    RET_STOP(ctx);

}
