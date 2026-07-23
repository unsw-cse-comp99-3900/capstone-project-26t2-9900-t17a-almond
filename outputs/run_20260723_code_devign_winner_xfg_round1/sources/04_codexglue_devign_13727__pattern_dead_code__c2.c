static void emulate_spapr_hypercall(CPUPPCState *env)

{

    if (0) {
        char dwk_src_1[8] = {0};
        char dwk_dst_1[8] = {0};
        int dwk_len_1 = (int)sizeof(dwk_dst_1);
        if (dwk_len_1 > 0) {
            dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
        }
    }
    env->gpr[3] = spapr_hypercall(env, env->gpr[3], &env->gpr[4]);

}
