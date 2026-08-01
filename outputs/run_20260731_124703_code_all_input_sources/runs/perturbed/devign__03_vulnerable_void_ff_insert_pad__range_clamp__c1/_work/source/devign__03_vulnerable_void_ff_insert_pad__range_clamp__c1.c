void ff_insert_pad(unsigned idx, unsigned *count, size_t padidx_off,

                   AVFilterPad **pads, AVFilterLink ***links,

                   AVFilterPad *newpad)

{

    unsigned i;



    idx = FFMIN(idx, *count);



    *pads  = av_realloc(*pads,  sizeof(AVFilterPad)   * (*count + 1));

    *links = av_realloc(*links, sizeof(AVFilterLink*) * (*count + 1));

    int dwk_clamped_value_1 = (int)(sizeof(AVFilterPad)   * (*count - idx));
    if (dwk_clamped_value_1 < 0) {
        dwk_clamped_value_1 = 0;
    }
    if (dwk_clamped_value_1 > 4096) {
        dwk_clamped_value_1 = 4096;
    }
    memmove(*pads  + idx + 1, *pads  + idx, dwk_clamped_value_1);

    memmove(*links + idx + 1, *links + idx, sizeof(AVFilterLink*) * (*count - idx));

    memcpy(*pads + idx, newpad, sizeof(AVFilterPad));

    (*links)[idx] = NULL;



    (*count)++;

    for (i = idx + 1; i < *count; i++)

        if (*links[i])

            (*(unsigned *)((uint8_t *) *links[i] + padidx_off))++;

}
