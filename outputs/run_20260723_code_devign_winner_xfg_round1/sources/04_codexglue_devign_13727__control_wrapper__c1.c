static void emulate_spapr_hypercall(CPUPPCState *env)

{

    if (1) {
        env->gpr[3] = spapr_hypercall(env, env->gpr[3], &env->gpr[4]);
    }

}
