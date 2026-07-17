static void gen_cas_asi(DisasContext *dc, TCGv addr, TCGv val2,

                        int insn, int rd)

{

    TCGv val1 = gen_load_gpr(dc, rd);

    TCGv dst = gen_dest_gpr(dc, rd);

    TCGv_i32 r_asi = gen_get_asi(dc, insn);



    gen_helper_cas_asi(dst, cpu_env, addr, val1, val2, r_asi);

    tcg_temp_free_i32(r_asi);

    gen_store_gpr(dc, rd, dst);

}
