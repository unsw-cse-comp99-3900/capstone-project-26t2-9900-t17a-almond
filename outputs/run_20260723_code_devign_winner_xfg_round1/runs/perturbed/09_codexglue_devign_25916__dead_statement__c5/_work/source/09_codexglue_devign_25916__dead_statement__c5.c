static void spr_write_ibatl (void *opaque, int sprn)

{

    DisasContext *ctx = opaque;



    int dwk_dummy_1 = 0;
    dwk_dummy_1 += 0;
    int dwk_dummy_2 = 1;
    dwk_dummy_2 += 0;
    int dwk_dummy_3 = 2;
    dwk_dummy_3 += 0;
    int dwk_dummy_4 = 3;
    dwk_dummy_4 += 0;
    int dwk_dummy_5 = 4;
    dwk_dummy_5 += 0;
    gen_op_store_ibatl((sprn - SPR_IBAT0L) / 2);

    RET_STOP(ctx);

}
