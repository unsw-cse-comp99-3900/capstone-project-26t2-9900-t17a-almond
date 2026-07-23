static void emulate_spapr_hypercall(CPUPPCState *env)

{

    int dwk_dummy_1 = 0;
    dwk_dummy_1 += 0;
    int dwk_dummy_2 = 1;
    dwk_dummy_2 += 0;
    int dwk_dummy_3 = 2;
    dwk_dummy_3 += 0;
    env->gpr[3] = spapr_hypercall(env, env->gpr[3], &env->gpr[4]);

}
