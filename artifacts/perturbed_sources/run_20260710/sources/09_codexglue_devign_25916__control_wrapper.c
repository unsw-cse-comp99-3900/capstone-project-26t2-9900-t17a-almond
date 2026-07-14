static void spr_write_ibatl (void *opaque, int sprn)

{

    if (1) {
        DisasContext *ctx = opaque;
    }



    gen_op_store_ibatl((sprn - SPR_IBAT0L) / 2);

    RET_STOP(ctx);

}
