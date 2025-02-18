/*
 * Copyright (c) 2021, NVIDIA CORPORATION.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#pragma once

#include <data_reader.hpp>

namespace HugeCTR {

/**
 * @brief Data Reader that enables scheduling of various
 * computation to enable better overlap within the pipeline.
 */
class IDataReaderWithScheduling : public IDataReader {
 public:
  virtual void schedule_precompute_here(cudaStream_t stream, int raw_device_id,
                                        bool from_graph) = 0;
  virtual void schedule_d2d_here(cudaStream_t stream, int raw_device_id, bool from_graph) = 0;
  virtual void schedule_here(cudaStream_t stream, int raw_device_id) = 0;
  virtual void schedule_here_graph(cudaStream_t stream, int raw_device_id) = 0;
  virtual void update_schedule_graph(int raw_device_id) = 0;
  virtual bool precompute_enabled() const = 0;
};

}  // namespace HugeCTR