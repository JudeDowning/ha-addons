ARG BUILD_FROM
FROM ${BUILD_FROM}

COPY --chmod=755 rootfs/run.sh /run.sh

ENTRYPOINT ["/run.sh"]
