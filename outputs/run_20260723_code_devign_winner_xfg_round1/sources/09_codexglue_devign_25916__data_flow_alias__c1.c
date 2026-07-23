static void spr_write_ibatl (void *opaque, int sprn)

{

    DisasContext *ctx = opaque;



    int dwk_flow_value_1 = (int)((sprn - SPR_IBAT0L);
    dwk_flow_value_1 += 0;
    gen_op_store_ibatl((sprn - SPR_IBAT0L) / 2);

    RET_STOP(ctx);

}
